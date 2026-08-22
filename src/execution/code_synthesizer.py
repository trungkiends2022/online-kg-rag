"""Sinh code Python thực thi 1 reasoning path, chỉ được gọi qua API giới hạn của kg."""

from __future__ import annotations

import json

from src.planning.planner import ReasoningPath
from src.llm.client import llm_call

KG_API_DOC = """
API khả dụng trên biến `kg` (đối tượng OnlineKG):
    kg.get_neighbors(entity: str, relation: str = None) -> list[str]
    kg.get_relations(entity: str) -> list[str]
    kg.filter(entities: list[str], predicate: Callable[[str], bool]) -> list[str]
Code PHẢI gán kết quả cuối cùng vào biến `result`.
Không được import, không được mở file, không được gọi network.
"""


class CodeSynthesizer:
    def synthesize(self, path: ReasoningPath, question: str) -> str:
        prompt = f"""
        Question: {question}
        Reasoning path: {json.dumps([s.__dict__ for s in path.steps], ensure_ascii=False)}
        {KG_API_DOC}

        Viết code Python thực hiện đúng reasoning path trên bằng cách gọi các hàm của `kg`.
        Chỉ trả về code, không giải thích, không markdown fence.
        """
        code = llm_call(prompt)
        return code.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()
