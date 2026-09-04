"""Hợp nhất triples từ table/text/web thành 1 OnlineKG, kèm entity resolution."""

from __future__ import annotations

from src.kg.online_kg import OnlineKG
from src.kg.normalization import EntityResolver
from src.kg.schema import Triple
from src.extraction.extractor import EntityRelationExtractor


class OnlineKGBuilder:
    def __init__(
        self,
        extractor: EntityRelationExtractor | None = None,
        entity_resolver: EntityResolver | None = None,
    ):
        self.extractor = extractor or EntityRelationExtractor()
        self.entity_resolver = entity_resolver or EntityResolver()

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

        self.entity_resolver.resolve(kg)
        return kg

    @staticmethod
    def _resolve_entities(kg: OnlineKG) -> None:
        """Backward-compatible entry point for callers using the old helper."""
        EntityResolver().resolve(kg)
