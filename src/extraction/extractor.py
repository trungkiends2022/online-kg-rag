"""Chuyển mọi nguồn (table row, text passage, web snippet) thành triples có provenance."""

from __future__ import annotations

import json

from src.kg.schema import Triple, Provenance
from src.llm.client import llm_call_json


_EXTRACT_INSTRUCTION = (
    'Trả về JSON list dạng [{{"head": ..., "relation": ..., "tail": ...}}, ...]. '
    "Chỉ trả JSON, không giải thích, không markdown fence."
)


class EntityRelationExtractor:
    def extract_from_table(self, table_name: str, rows: list[dict]) -> list[Triple]:
        prompt = f"""
        Table name: {table_name}
        Rows (JSON): {json.dumps(rows, ensure_ascii=False)}

        Trích xuất các triple (head, relation, tail) biểu diễn nội dung các dòng này.
        {_EXTRACT_INSTRUCTION}
        """
        items = llm_call_json(prompt)
        return [
            Triple(
                head=it["head"], relation=it["relation"], tail=it["tail"],
                provenance=Provenance("table", table_name, json.dumps(rows, ensure_ascii=False)[:200]),
            )
            for it in items
        ]

    def extract_from_text(self, passage_id: str, text: str) -> list[Triple]:
        prompt = f"""
        Passage: {text}
        Trích xuất các triple (head, relation, tail) thể hiện fact trong đoạn văn.
        {_EXTRACT_INSTRUCTION}
        """
        items = llm_call_json(prompt)
        return [
            Triple(
                head=it["head"], relation=it["relation"], tail=it["tail"],
                provenance=Provenance("text", passage_id, text[:200]),
            )
            for it in items
        ]

    def extract_from_web(self, url: str, snippet: str) -> list[Triple]:
        prompt = f"""
        Web snippet (nguồn: {url}): {snippet}
        Trích xuất các triple (head, relation, tail).
        {_EXTRACT_INSTRUCTION}
        """
        items = llm_call_json(prompt)
        return [
            Triple(
                head=it["head"], relation=it["relation"], tail=it["tail"],
                provenance=Provenance("web", url, snippet[:200]),
            )
            for it in items
        ]
