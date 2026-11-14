"""Hợp nhất triples từ table/text/web thành 1 OnlineKG, kèm entity resolution."""

from __future__ import annotations

from dataclasses import replace
import re

from src.kg.online_kg import OnlineKG
from src.kg.normalization import EntityResolver, normalize_relation
from src.kg.schema import Provenance, Triple
from src.extraction.extractor import EntityRelationExtractor


# These relations state that a compound subject became the object.  They are
# intentionally narrow: splitting every relation containing "and" would turn
# ordinary entity names (for example, Research and Development) into false KG
# facts.
COMPOUND_MERGER_RELATIONS = frozenset({
    "merged_to_form",
    "merged_to_create",
    "merged_to_become",
})


def _compound_members(value: str) -> list[str]:
    """Split a merger subject only when it clearly enumerates two+ entities."""
    members = [
        member.strip()
        for member in re.split(r"\s*(?:,|;|\band\b|&)\s*", str(value), flags=re.IGNORECASE)
        if member.strip()
    ]
    unique = list(dict.fromkeys(members))
    return unique if 2 <= len(unique) <= 5 else []


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
            row_indices = row_group.get("row_indices")
            cell_links = row_group.get("cell_links", [])
            kg.register_table_structure(
                table_name, rows, row_indices=row_indices, cell_links=cell_links,
            )
            # Tables preserve their schema deterministically; semantic
            # enrichment comes exclusively from retrieved text passages.
            all_triples += self.extractor.extract_from_table(
                table_name, rows, use_llm_enrichment=False,
                row_indices=row_indices,
            )
            all_triples += self._table_geographic_triples(
                table_name, rows, row_indices=row_indices, cell_links=cell_links,
            )
            all_triples += self._table_link_triples(table_name, cell_links)
        text_passages = list(retrieved.get("text_passages", []))
        for passage in text_passages:
            kg.register_passage(
                str(passage["id"]),
                str(passage["text"]),
                context_before=str(passage.get("context_before", "")),
            )
        if text_passages:
            uses_legacy_text_hook = (
                type(self.extractor).extract_from_text
                is not EntityRelationExtractor.extract_from_text
            )
            if uses_legacy_text_hook:
                # Keep bespoke extractors source-isolated: one bad passage must
                # not discard facts returned for the rest of the batch.
                for passage in text_passages:
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
            else:
                try:
                    all_triples += self.extractor.extract_from_text_batch(text_passages)
                except Exception as exc:
                    kg.extraction_errors.append({
                        "source_type": "text_batch",
                        "source_id": [str(passage["id"]) for passage in text_passages],
                        "error": f"{type(exc).__name__}: {exc}", "fallback": "skip_batch",
                    })
        for snippet in retrieved.get("web_snippets", []):
            try:
                all_triples += self.extractor.extract_from_web(snippet["url"], snippet["text"])
            except Exception as exc:
                kg.extraction_errors.append({
                    "source_type": "web", "source_id": snippet["url"],
                    "error": f"{type(exc).__name__}: {exc}", "fallback": "skip_source",
                })

        all_triples = self._administrative_bridges(all_triples)
        for t in self._expand_compound_mergers(all_triples):
            kg.add_triple(t)

        self.entity_resolver.resolve(kg)
        return kg

    @staticmethod
    def _expand_compound_mergers(triples: list[Triple]) -> list[Triple]:
        """Add auditable reverse edges for an explicit text merger fact.

        For ``A and B merged_to_form new C``, the source triple is retained and
        we add ``new C formed_from A`` and ``new C formed_from B``.  This makes
        both merger members reachable without inventing a relation from shared
        passage context alone.  EntityResolver may subsequently canonicalize
        ``new C`` to an evidenced same-passage ``C``.
        """
        expanded = list(triples)
        known = {
            (str(t.head), normalize_relation(t.relation), str(t.tail))
            for t in triples
        }
        for triple in triples:
            relation = normalize_relation(triple.relation)
            if (
                triple.provenance.source_type != "text"
                or relation not in COMPOUND_MERGER_RELATIONS
            ):
                continue
            for member in _compound_members(str(triple.head)):
                key = (str(triple.tail), "formed_from", member)
                if key in known:
                    continue
                expanded.append(Triple(
                    head=str(triple.tail),
                    relation="formed_from",
                    tail=member,
                    provenance=replace(
                        triple.provenance,
                        derived_from_compound=True,
                    ),
                ))
                known.add(key)
        return expanded

    @staticmethod
    def _table_geographic_triples(
        table_name: str, rows: list[dict], *, row_indices: list[int] | None = None,
        cell_links: list[dict] | None = None,
    ) -> list[Triple]:
        """Expose a table's locality-to-administrative-area facts as KG edges.

        Row records preserve this relationship structurally, but path search
        needs an explicit semantic bridge such as ``suburb --located_in--> LGA``
        to continue from a linked locality into demographic text evidence.
        """
        triples: list[Triple] = []
        locality_re = re.compile(r"\b(suburb|locality|town|city|village)\b", re.I)
        area_re = re.compile(r"\b(lga|local government|region|district|council|municipality)\b", re.I)
        links_by_cell: dict[tuple[int, str, str], list[str]] = {}
        for link in cell_links or []:
            key = (int(link.get("row_index", -1)), str(link.get("column_name", "")), str(link.get("cell_value", "")))
            links_by_cell.setdefault(key, []).append(str(link.get("url", "")))
        for index, row in enumerate(rows):
            row_index = row_indices[index] if row_indices and index < len(row_indices) else index
            localities = [str(value).strip() for column, value in row.items()
                          if locality_re.search(str(column)) and str(value).strip()]
            areas = [(str(column), str(value).strip()) for column, value in row.items()
                     if area_re.search(str(column)) and str(value).strip()]
            for locality in localities:
                for column, area in areas:
                    labels = [area, *OnlineKG.split_cell_entities(
                        area, links_by_cell.get((int(row_index), column, area), []),
                    )]
                    for label in dict.fromkeys(labels):
                        if locality.casefold() == label.casefold():
                            continue
                        triples.append(Triple(
                            locality, "located_in", label,
                        Provenance("table", table_name, f"{locality} -> {area}",
                                   row_index=row_index, column_name=column,
                                   header_path=(column,)),
                        ))
        return triples

    @staticmethod
    def _administrative_key(value: str) -> str:
        """Match a Region label to its Regional Council without merging nodes."""
        key = re.sub(r"\bregional\b", "region", str(value).casefold())
        key = re.sub(r"\b(?:council|municipality|district)\b", "", key)
        return " ".join(re.findall(r"[a-z0-9]+", key))

    @classmethod
    def _administrative_bridges(cls, triples: list[Triple]) -> list[Triple]:
        """Connect a table administrative area to its text demographic body.

        This is intentionally narrow: an administrative bridge is emitted only
        when a text fact has a ``population`` relation and both labels reduce to
        the same administrative key (e.g. MacDonnell Region / MacDonnell
        Regional Council).  The two nodes remain distinct and auditable.
        """
        areas = [triple for triple in triples if triple.relation == "located_in"
                 and triple.provenance.source_type == "table"]
        population_heads = [triple for triple in triples if triple.relation == "population"
                            and triple.provenance.source_type == "text"]
        known = {(str(triple.head), str(triple.relation), str(triple.tail)) for triple in triples}
        bridged = list(triples)
        for area_edge in areas:
            area_key = cls._administrative_key(area_edge.tail)
            if not area_key:
                continue
            for population in population_heads:
                if area_key != cls._administrative_key(population.head):
                    continue
                key = (str(area_edge.tail), "administered_by", str(population.head))
                if key in known:
                    continue
                bridged.append(Triple(
                    area_edge.tail, "administered_by", population.head,
                    replace(population.provenance, raw_snippet=f"administrative name bridge: {area_edge.tail}"),
                ))
                known.add(key)
        return bridged

    @staticmethod
    def _table_link_triples(table_name: str, cell_links: list[dict]) -> list[Triple]:
        """Keep HybridQA cell hyperlinks as deterministic table-to-text facts."""
        triples = []
        for link in cell_links:
            value, url = str(link.get("cell_value", "")), str(link.get("url", ""))
            if not value.strip() or not url.strip():
                continue
            column_name = link.get("column_name")
            triples.append(Triple(
                value, "linked_passage", url,
                Provenance(
                    "table", table_name, url,
                    row_index=link.get("row_index"),
                    column_name=column_name,
                    header_path=(str(column_name),) if column_name else None,
                ),
            ))
            for member in OnlineKG.split_cell_entities(value, [url]):
                if member == value:
                    continue
                triples.append(Triple(
                    member, "linked_passage", url,
                    Provenance(
                        "table", table_name, url,
                        row_index=link.get("row_index"),
                        column_name=column_name,
                        header_path=(str(column_name),) if column_name else None,
                    ),
                ))
        return triples

    @staticmethod
    def _resolve_entities(kg: OnlineKG) -> None:
        """Backward-compatible entry point for callers using the old helper."""
        EntityResolver().resolve(kg)
