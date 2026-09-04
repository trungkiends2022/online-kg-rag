"""Sinh code Python thực thi 1 reasoning path, chỉ được gọi qua API giới hạn của kg."""

from __future__ import annotations

import json

from src.planning.planner import ReasoningPath
from src.llm.client import llm_call

KG_API_DOC = """
API khả dụng trên biến `kg` (đối tượng OnlineKG):
    kg.get_neighbors(entity: str, relation: str = None) -> list[str]
    kg.get_sources(entity: str, relation: str = None) -> list[str]
    kg.get_relations(entity: str) -> list[str]
    kg.filter(entities: list[str], predicate: Callable[[str], bool]) -> list[str]
Code PHẢI gán kết quả cuối cùng vào biến `result`.
Không được import, không được mở file, không được gọi network.
`get_neighbors` đi từ head tới tail; `get_sources` đi ngược từ tail về head.
Tên relation được chuẩn hóa tự động (camelCase/space/snake_case).
"""


class CodeSynthesizer:
    def synthesize(self, path: ReasoningPath, question: str, retries: int = 1) -> str:
        base_prompt = f"""
        Question: {question}
        Reasoning path: {json.dumps([s.__dict__ for s in path.steps], ensure_ascii=False)}
        {KG_API_DOC}

        Viết code Python thực hiện đúng reasoning path trên bằng cách gọi các hàm của `kg`.
        Chỉ trả về code, không giải thích, không markdown fence.
        """
        last_code = ""
        last_error = "empty code"
        for attempt in range(retries + 1):
            prompt = base_prompt
            if attempt:
                prompt += (
                    f"\nCode trước không hợp lệ ({last_error}):\n{last_code}\n"
                    "Viết lại code hoàn chỉnh, hợp lệ và phải gán biến result."
                )
            raw = llm_call(prompt)
            last_code = raw.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()
            if not last_code:
                last_error = "empty code"
                continue
            try:
                compile(last_code, "<llm-generated>", "exec")
            except SyntaxError as exc:
                last_error = f"SyntaxError: {exc.msg} at line {exc.lineno}"
                continue
            if "result" not in last_code:
                last_error = "missing result assignment"
                continue
            return last_code
        raise ValueError(f"LLM không sinh được code hợp lệ sau {retries + 1} lần: {last_error}")
