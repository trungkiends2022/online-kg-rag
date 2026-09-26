"""Chuyển mọi nguồn (table row, text passage, web snippet) thành triples có provenance."""

from __future__ import annotations

import json
import re

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
    def __init__(
        self,
        table_batch_size: int = 5,
        text_batch_size: int = 5,
        json_retries: int = 2,
        temperature: float | None = None,
        max_output_tokens: int = 4096,
        use_llm_text_enrichment: bool = True,
    ):
        if table_batch_size < 1:
            raise ValueError("table_batch_size must be at least 1")
        if text_batch_size < 1:
            raise ValueError("text_batch_size must be at least 1")
        if json_retries < 0:
            raise ValueError("json_retries must be non-negative")
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        self.table_batch_size = table_batch_size
        self.text_batch_size = text_batch_size
        self.json_retries = json_retries
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.use_llm_text_enrichment = use_llm_text_enrichment

    def _call_json(self, prompt: str, max_tokens: int):
        kwargs = {"max_tokens": max_tokens, "retries": self.json_retries}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        return llm_call_json(prompt, **kwargs)

    def extract_from_table(
        self, table_name: str, rows: list[dict], *,
        use_llm_enrichment: bool = False,
        row_indices: list[int] | None = None,
    ) -> list[Triple]:
        # HybridQA tables commonly contain 5-20 rows. Asking for every cell as
        # triples in one response can exceed the model's output-token budget and
        # leave a syntactically truncated JSON array, so process bounded batches.
        batches = [
            rows[start:start + self.table_batch_size]
            for start in range(0, len(rows), self.table_batch_size)
        ] or [[]]
        triples = []
        for batch_index, batch in enumerate(batches):
            raw_batch = json.dumps(batch, ensure_ascii=False)
            provenance = Provenance("table", table_name, raw_batch[:200])
            # Preserve the table schema deterministically. The first column is
            # the row entity and every remaining column becomes a qualified
            # relation (e.g. 2002_dividend), independent of LLM extraction.
            for local_row_index, row in enumerate(batch):
                cells = list(row.items())
                if not cells:
                    continue
                _, head = cells[0]
                if str(head).strip() == "":
                    continue
                selected_index = batch_index * self.table_batch_size + local_row_index
                original_row_index = (
                    row_indices[selected_index]
                    if row_indices is not None and selected_index < len(row_indices)
                    else selected_index
                )
                for relation, tail in cells[1:]:
                    if str(tail).strip() == "":
                        continue
                    header_path = tuple(
                        part for part in str(relation).replace("__", "_").split("_") if part
                    )
                    cell_provenance = Provenance(
                        "table",
                        table_name,
                        str(tail)[:200],
                        row_index=original_row_index,
                        column_name=str(relation),
                        header_path=header_path,
                    )
                    triples.append(_triple_from_item({
                        "head": head,
                        "relation": relation,
                        "tail": tail,
                    }, cell_provenance))
            if not use_llm_enrichment:
                continue
            prompt = f"""
        Table name: {table_name} (batch {batch_index + 1}/{len(batches)})
        Rows (JSON): {json.dumps(batch, ensure_ascii=False)}

        Trích xuất các triple (head, relation, tail) biểu diễn nội dung các dòng này.
        {_EXTRACT_INSTRUCTION}
        """
            items = self._call_json(prompt, max_tokens=self.max_output_tokens)
            triples.extend(_triple_from_item(item, provenance) for item in items)
        return triples

    def extract_from_text(
        self, passage_id: str, text: str, *, context_before: str = ""
    ) -> list[Triple]:
        context_note = (
            f"Previous context (resolve pronouns/subject only): {context_before}\n"
            if context_before else ""
        )
        prompt = f"""
        {context_note}
        Passage: {text}
        Trích xuất các triple (head, relation, tail) thể hiện fact trong đoạn văn.
        {_EXTRACT_INSTRUCTION}
        """
        provenance = Provenance("text", passage_id, text[:200])
        items = []
        if self.use_llm_text_enrichment:
            # Deterministic facts below remain useful even when optional LLM
            # enrichment returns malformed JSON.
            try:
                items = self._call_json(prompt, max_tokens=self.max_output_tokens)
            except Exception:
                items = []
        triples = [_triple_from_item(it, provenance) for it in items]
        return [
            *triples,
            *self._deterministic_text_triples(passage_id, text, context_before=context_before),
        ]

    def extract_from_text_batch(self, passages: list[dict]) -> list[Triple]:
        """Extract text facts in bounded batches, preserving passage provenance.

        A batch of five is one request for the ordinary HybridQA first-stage
        retrieval set. Each returned fact must carry ``source_id`` so a batch
        cannot accidentally attribute a fact to the wrong passage.
        """
        if not passages:
            return []
        # Keep custom test/domain extractors that override the single-passage
        # hook compatible; production uses the batched base implementation.
        if type(self).extract_from_text is not EntityRelationExtractor.extract_from_text:
            return [
                triple
                for passage in passages
                for triple in self.extract_from_text(
                    str(passage["id"]), str(passage["text"]),
                    context_before=str(passage.get("context_before", "")),
                )
            ]

        triples = []
        for start in range(0, len(passages), self.text_batch_size):
            batch = passages[start:start + self.text_batch_size]
            if self.use_llm_text_enrichment:
                payload = [
                    {
                        "source_id": str(passage["id"]),
                        "text": str(passage["text"]),
                        "context_before": str(passage.get("context_before", "")),
                    }
                    for passage in batch
                ]
                prompt = f"""
Passages (JSON): {json.dumps(payload, ensure_ascii=False)}

Trích xuất fact trong từng passage. Mỗi item PHẢI giữ đúng source_id của
passage chứa fact; không suy luận fact giữa các passage.
Trả về JSON list dạng [{{"source_id": ..., "head": ..., "relation": ..., "tail": ...}}, ...].
Chỉ trả JSON, không giải thích, không markdown fence.
"""
                try:
                    items = self._call_json(prompt, max_tokens=self.max_output_tokens)
                except Exception:
                    items = []
                allowed = {str(passage["id"]): passage for passage in batch}
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    source_id = str(item.get("source_id", ""))
                    if source_id not in allowed or not {"head", "relation", "tail"} <= item.keys():
                        continue
                    passage = allowed[source_id]
                    triples.append(_triple_from_item(
                        item, Provenance("text", source_id, str(passage["text"])[:200]),
                    ))
            for passage in batch:
                triples.extend(self._deterministic_text_triples(
                    str(passage["id"]), str(passage["text"]),
                    context_before=str(passage.get("context_before", "")),
                ))
        return triples

    @staticmethod
    def _deterministic_text_triples(
        passage_id: str, text: str, *, context_before: str = "",
    ) -> list[Triple]:
        """Facts retained even when text LLM enrichment is disabled or fails."""
        provenance = Provenance("text", passage_id, text[:200])
        triples = []

        # Biography passages commonly open with a three-token legal name, while
        # the linked table uses only first + last name. Preserve this bridge
        # deterministically so entity-centric paths can derive a middle name
        # without depending on an extractor choosing the exact ``full_name``
        # relation wording.
        name_match = re.match(
            r"\s*([A-Z][\w'’-]+\s+[A-Z][\w'’-]+\s+[A-Z][\w'’-]+)\s*\(", text
        )
        if name_match:
            full_name = name_match.group(1)
            parts = full_name.split()
            triples.insert(0, Triple(
                head=f"{parts[0]} {parts[-1]}", relation="full_name", tail=full_name,
                provenance=provenance,
            ))

        # Preserve a typed and scoped annual-interest fact independently of LLM
        # relation wording. FinQA often splits its subject and amount across two
        # adjacent sentences, which otherwise collapses several unrelated
        # "interest" amounts onto the same generic KG node.
        amount_match = re.search(
            r"interest(?:\s+on\s+the\s+([^,.]+?))?\s+(?:of\s+)?(?:approximately\s+)?"
            r"(\$\s*[\d,.]+\s+million\s+per\s+year)",
            text,
            flags=re.IGNORECASE,
        )
        if amount_match:
            subject = (amount_match.group(1) or "").strip()
            if not subject:
                antecedents = re.findall(r"\b(20\d{2}\s+notes)\b", context_before, re.I)
                subject = antecedents[-1] if antecedents else "interest"
            triples.insert(0, Triple(
                head=subject,
                relation="annual_interest_amount",
                tail=amount_match.group(2),
                provenance=provenance,
            ))
            triples.insert(1, Triple(
                head=subject,
                relation="payment_frequency",
                tail="annual",
                provenance=provenance,
            ))
        # Financial prose frequently gives a current value and the absolute
        # change from an earlier period in one sentence. Preserve both values
        # with explicit temporal relations so an executable program can derive
        # the earlier value instead of selecting a same-named table row.
        change_match = re.search(
            r"(?P<head>[a-z][a-z\s-]{2,}?)\s+increased\s+\$?\s*"
            r"(?P<delta>[\d,.]+)\s+million.*?\s+from\s+(?P<start>20\d{2})\s+"
            r"to\s+\$?\s*(?P<end_value>[\d,.]+)\s+(?P<unit>billion|million)\s+"
            r"in\s+(?P<end>20\d{2})",
            text,
            flags=re.IGNORECASE,
        )
        if change_match:
            head = change_match.group("head").strip()
            triples.extend([
                Triple(head, f"value_{change_match.group('end')}",
                       f"${change_match.group('end_value')} {change_match.group('unit')}", provenance),
                Triple(head, f"increase_from_{change_match.group('start')}_to_{change_match.group('end')}",
                       f"${change_match.group('delta')} million", provenance),
            ])
        return triples

    def extract_from_web(self, url: str, snippet: str) -> list[Triple]:
        prompt = f"""
        Web snippet (nguồn: {url}): {snippet}
        Trích xuất các triple (head, relation, tail).
        {_EXTRACT_INSTRUCTION}
        """
        items = self._call_json(prompt, max_tokens=self.max_output_tokens)
        provenance = Provenance("web", url, snippet[:200])
        return [_triple_from_item(it, provenance) for it in items]
