"""Sinh N candidate reasoning path độc lập trên OnlineKG (chỉ kế hoạch, chưa sinh code)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from src.kg.online_kg import OnlineKG
from src.llm.client import llm_call_json


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
    def generate_candidates(self, question: str, kg: OnlineKG, n: int = 5) -> list[ReasoningPath]:
        summary = kg.summary()
        prompt = f"""
        Question: {question}
        Entities có trong KG tạm (mẫu, tối đa 50): {list(kg.graph.nodes())[:50]}
        Relations có trong KG tạm: {summary["relations"][:50]}

        Sinh {n} reasoning path KHÁC NHAU (không phải code, chỉ là kế hoạch các bước)
        để trả lời câu hỏi trên bằng cách truy vấn KG này.
        Mỗi path là 1 list các step: {{"step": int, "goal": str, "depends_on": int|null}}
        Trả về JSON: [{{"path_id": str, "steps": [...]}}, ...]
        Chỉ trả JSON.
        """
        items = llm_call_json(prompt)
        paths = []
        for item in items:
            steps = [PathStep(**s) for s in item["steps"]]
            paths.append(ReasoningPath(path_id=item.get("path_id", str(uuid.uuid4())[:8]), steps=steps))
        return paths
