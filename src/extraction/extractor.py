"""Chuyển mọi nguồn (table row, text passage, web snippet) thành triples có provenance."""

from __future__ import annotations

import json

from src.kg.schema import Triple, Provenance
from src.llm.client import llm_call_json


_EXTRACT_INSTRUCTION = (
    'Trả về JSON list dạng [{{"head": ..., "relation": ..., "tail": ...}}, ...]. '
    "Chỉ trả JSON, không giải thích, không markdown fence."
)


def _triple_from_item(item: dict, provenance: Provenance) -> Triple:
    """Normalize scalar JSON values returned by an LLM to the KG string schema."""
    return Triple(
        head=str(item["head"]),
        relation=str(item["relation"]),
        tail=str(item["tail"]),
        provenance=provenance,
    )


class EntityRelationExtractor:
    def __init__(self, table_batch_size: int = 5):
        if table_batch_size < 1:
            raise ValueError("table_batch_size must be at least 1")
        self.table_batch_size = table_batch_size

    def extract_from_table(self, table_name: str, rows: list[dict]) -> list[Triple]:
        # HybridQA tables commonly contain 5-20 rows. Asking for every cell as
        # triples in one response can exceed the model's output-token budget and
        # leave a syntactically truncated JSON array, so process bounded batches.
        batches = [
            rows[start:start + self.table_batch_size]
            for start in range(0, len(rows), self.table_batch_size)
        ] or [[]]
        triples = []
        for batch_index, batch in enumerate(batches):
            prompt = f"""
        Table name: {table_name} (batch {batch_index + 1}/{len(batches)})
        Rows (JSON): {json.dumps(batch, ensure_ascii=False)}

        Trích xuất các triple (head, relation, tail) biểu diễn nội dung các dòng này.
        {_EXTRACT_INSTRUCTION}
        """
            items = llm_call_json(prompt, max_tokens=4096)
            provenance = Provenance(
                "table", table_name, json.dumps(batch, ensure_ascii=False)[:200]
            )
            triples.extend(_triple_from_item(item, provenance) for item in items)
        return triples

    def extract_from_text(self, passage_id: str, text: str) -> list[Triple]:
        prompt = f"""
        Passage: {text}
        Trích xuất các triple (head, relation, tail) thể hiện fact trong đoạn văn.
        {_EXTRACT_INSTRUCTION}
        """
        items = llm_call_json(prompt, max_tokens=2048)
        provenance = Provenance("text", passage_id, text[:200])
        return [_triple_from_item(it, provenance) for it in items]

    def extract_from_web(self, url: str, snippet: str) -> list[Triple]:
        prompt = f"""
        Web snippet (nguồn: {url}): {snippet}
        Trích xuất các triple (head, relation, tail).
        {_EXTRACT_INSTRUCTION}
        """
        items = llm_call_json(prompt, max_tokens=2048)
        provenance = Provenance("web", url, snippet[:200])
        return [_triple_from_item(it, provenance) for it in items]
