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
            table_name = row_group.get("table_name", "unknown_table")
            rows = row_group.get("rows", [])
            try:
                all_triples += self.extractor.extract_from_table(
                    table_name, rows,
                    use_llm_enrichment=not row_group.get("deterministic_only", False),
                )
            except Exception as exc:
                # Cell triples do not depend on model output; retain them when
                # optional LLM table enrichment is malformed.
                all_triples += self.extractor.extract_from_table(
                    table_name, rows, use_llm_enrichment=False,
                )
                kg.extraction_errors.append({
                    "source_type": "table", "source_id": table_name,
                    "error": f"{type(exc).__name__}: {exc}", "fallback": "deterministic_cells",
                })
        for passage in retrieved.get("text_passages", []):
            try:
                all_triples += self.extractor.extract_from_text(
                    passage["id"], passage["text"],
                    context_before=passage.get("context_before", ""),
                )
            except Exception as exc:
                kg.extraction_errors.append({
                    "source_type": "text", "source_id": passage["id"],
                    "error": f"{type(exc).__name__}: {exc}", "fallback": "skip_source",
                })
        for snippet in retrieved.get("web_snippets", []):
            try:
                all_triples += self.extractor.extract_from_web(snippet["url"], snippet["text"])
            except Exception as exc:
                kg.extraction_errors.append({
                    "source_type": "web", "source_id": snippet["url"],
                    "error": f"{type(exc).__name__}: {exc}", "fallback": "skip_source",
                })

        for t in all_triples:
            kg.add_triple(t)

        self.entity_resolver.resolve(kg)
        return kg

    @staticmethod
    def _resolve_entities(kg: OnlineKG) -> None:
        """Backward-compatible entry point for callers using the old helper."""
        EntityResolver().resolve(kg)
