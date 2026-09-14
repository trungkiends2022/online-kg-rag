"""Sinh N candidate reasoning path độc lập trên OnlineKG (chỉ kế hoạch, chưa sinh code)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from src.kg.online_kg import OnlineKG
from src.llm.client import llm_call_json
from src.planning.operation_intent import format_operation_intent, infer_operation_intent


@dataclass
class PathStep:
    step: int
    goal: str
    depends_on: Optional[int] = None


@dataclass
class ReasoningPath:
    path_id: str
    steps: list[PathStep]


class PathPlanner:
    def __init__(self, temperature: float | None = None):
        self.temperature = temperature

    def generate_candidates(self, question: str, kg: OnlineKG, n: int = 5) -> list[ReasoningPath]:
        summary = kg.summary()
        operation_intent = infer_operation_intent(question, kg)
        prompt = f"""
        Question: {question}
        Entities có trong KG tạm (mẫu, tối đa 50): {list(kg.graph.nodes())[:50]}
        Relations có trong KG tạm: {summary["relations"][:50]}
        Numerical operation intent inferred from question and KG schema only:
        {format_operation_intent(operation_intent)}

        Sinh {n} reasoning path KHÁC NHAU (không phải code, chỉ là kế hoạch các bước)
        để trả lời câu hỏi trên bằng cách truy vấn KG này.
        Với thay đổi theo thời gian "from A to B", giữ dấu và tính B - A;
        không tự đổi thành độ lớn dương chỉ vì câu hỏi dùng từ increase/decline.
        Tuân thủ operation intent ở trên. Không thay một phép cộng các percentage
        cell có sẵn bằng weighted average/count-derived rate nếu câu hỏi không yêu
        cầu denominator.
        Mỗi path là 1 list các step: {{"step": int, "goal": str, "depends_on": int|null}}
        Trả về JSON: [{{"path_id": str, "steps": [...]}}, ...]
        Chỉ trả JSON.
        """
        # Multiple paths can easily exceed the generic 1024-token response limit,
        # especially for models that spend output tokens on internal reasoning.
        kwargs = {"max_tokens": 4096}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        items = llm_call_json(prompt, **kwargs)
        paths = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("steps"), list):
                continue
            steps = []
            for index, raw_step in enumerate(item["steps"], start=1):
                if not isinstance(raw_step, dict):
                    continue
                goal = raw_step.get("goal")
                if not isinstance(goal, str) or not goal.strip():
                    continue
                raw_number = raw_step.get("step", index)
                raw_dependency = raw_step.get("depends_on")
                try:
                    step_number = int(raw_number)
                    dependency = int(raw_dependency) if raw_dependency is not None else None
                except (TypeError, ValueError):
                    continue
                # Providers occasionally add useful-looking fields such as
                # ``operator`` or ``result`` despite the requested schema. Keep
                # the planner contract stable by accepting only known fields.
                steps.append(PathStep(step=step_number, goal=goal.strip(), depends_on=dependency))
            if not steps:
                continue
            paths.append(ReasoningPath(path_id=item.get("path_id", str(uuid.uuid4())[:8]), steps=steps))
        return paths
