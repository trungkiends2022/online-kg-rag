"""Hợp nhất triples từ table/text/web thành 1 OnlineKG, kèm entity resolution."""

from __future__ import annotations

from collections import defaultdict

from src.kg.online_kg import OnlineKG
from src.kg.schema import Triple
from src.extraction.extractor import EntityRelationExtractor


class OnlineKGBuilder:
    def __init__(self, extractor: EntityRelationExtractor | None = None):
        self.extractor = extractor or EntityRelationExtractor()

    def build(self, retrieved: dict) -> OnlineKG:
        kg = OnlineKG()
        all_triples: list[Triple] = []

        for row_group in retrieved.get("table_rows", []):
            all_triples += self.extractor.extract_from_table(
                row_group.get("table_name", "unknown_table"), row_group.get("rows", [])
            )
        for passage in retrieved.get("text_passages", []):
            all_triples += self.extractor.extract_from_text(passage["id"], passage["text"])
        for snippet in retrieved.get("web_snippets", []):
            all_triples += self.extractor.extract_from_web(snippet["url"], snippet["text"])

        for t in all_triples:
            kg.add_triple(t)

        self._resolve_entities(kg)
        return kg

    @staticmethod
    def _resolve_entities(kg: OnlineKG) -> None:
        """
        Entity resolution baseline (case-insensitive match). Với dữ liệu thật, nên
        nâng cấp: LLM-based dedup, hoặc embedding similarity + threshold.
        """
        buckets: dict[str, list[str]] = defaultdict(list)
        for n in kg.graph.nodes():
            buckets[n.strip().lower()].append(n)
        for group in buckets.values():
            if len(group) > 1:
                canonical = max(group, key=len)
                kg.merge_entities(canonical, [g for g in group if g != canonical])
