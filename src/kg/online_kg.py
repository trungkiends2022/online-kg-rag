"""KG tạm dựng per-query (online/on-the-fly), khác với Hydra gốc (dùng Freebase/Wikidata offline).

API public trên đối tượng này chính là những gì code do LLM sinh ra được phép gọi
trong SandboxExecutor -- xem src/execution/sandbox.py.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

from typing import Callable, Optional

import networkx as nx

from src.kg.schema import EvidenceRef, Triple, Provenance
from src.kg.normalization import normalize_key, normalize_relation


class OnlineKG:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        # The executable graph remains value-centric for the sandbox API.  A
        # parallel typed structural trace preserves table/text topology for
        # audit, retrieval analysis and path ablations without polluting the
        # semantic entity graph with implementation IDs.
        self.node_types: dict[str, set[str]] = {}
        # Text passages enrich semantic nodes/edges through compact context
        # records. A node may be mentioned by multiple retrieved passages.
        self.text_contexts: dict[str, dict] = {}
        self.node_contexts: dict[str, list[dict]] = {}
        self.structural_nodes: dict[str, dict] = {}
        self.structural_edges: list[dict] = []
        # Row-record edges form the path-text reasoning view. They preserve
        # same-row bindings without changing the legacy executable graph API.
        self.record_edges: list[dict] = []
        self._passage_mention_keys: set[tuple[str, str]] = set()
        self.entity_aliases: dict[str, str] = {}
        self.entity_key_aliases: dict[str, str] = {}
        self.resolution_log: list[dict] = []
        self.rejection_log: list[dict] = []
        self.extraction_errors: list[dict] = []

    # ---- xây dựng ----
    def add_triple(self, triple: Triple) -> None:
        if normalize_key(triple.head) == normalize_key(triple.tail):
            self.rejection_log.append({
                "reason": "self_loop",
                "head": triple.head,
                "relation": self.normalize_relation(triple.relation),
                "tail": triple.tail,
            })
            return
        self.graph.add_node(triple.head)
        self.graph.add_node(triple.tail)
        self.node_types.setdefault(str(triple.head), set()).add("Entity")
        self.node_types.setdefault(str(triple.tail), set()).add("Attribute")
        context = None
        if triple.provenance.source_type == "text":
            context = self.text_contexts.get(str(triple.provenance.source_id))
            if context is not None:
                self._add_node_context(str(triple.head), context)
                self._add_node_context(str(triple.tail), context)
                self._register_passage_mentions(
                    str(triple.provenance.source_id), str(triple.head), str(triple.tail), context,
                )
        elif self.normalize_relation(triple.relation) == "linked_passage":
            context = self.text_contexts.get(str(triple.tail))
            if context is not None:
                self._add_node_context(str(triple.head), context)

        self.graph.add_edge(
            triple.head, triple.tail,
            relation=self.normalize_relation(triple.relation),
            provenance=triple.provenance,
            contexts=[dict(context)] if context is not None else [],
        )

    def _add_node_context(self, node: str, context: dict) -> None:
        contexts = self.node_contexts.setdefault(str(node), [])
        context_key = (context.get("source_id"), context.get("text"))
        if not any(
            (item.get("source_id"), item.get("text")) == context_key
            for item in contexts
        ):
            contexts.append(dict(context))

    def _register_passage_mentions(
        self, passage_id: str, head: str, tail: str, context: dict,
    ) -> None:
        """Expose a text passage as a structural bridge for linked table cells."""
        passage_node = f"passage:{passage_id}"
        for entity in (head, tail):
            key = (passage_id, entity)
            if key in self._passage_mention_keys:
                continue
            self._passage_mention_keys.add(key)
            self.record_edges.append({
                "head": passage_node,
                "relation": "mentions",
                "tail": entity,
                "source_type": "text",
                "source_id": passage_id,
                "row_index": None,
                "column_name": None,
                "header_path": None,
                "structural": True,
                "contexts": [dict(context)],
            })


    @staticmethod
    def split_cell_entities(value: str, urls: list[str] | tuple[str, ...] = ()) -> list[str]:
        """Return atomic entities explicitly encoded in a multi-value cell.

        Tokenized HybridQA cells can collapse several people into one display
        value. Separators are safe evidence; linked Wikipedia URLs add the
        original entity labels when whitespace has already been flattened.
        """
        raw = str(value).strip()
        members = [
            part.strip()
            for part in re.split(r"\s*(?:/|;|\||\n)\s*", raw)
            if part.strip() and re.search(r"[A-Za-z]", part)
        ]
        for url in urls:
            suffix = unquote(str(url).rstrip("/").rsplit("/", 1)[-1])
            label = re.sub(r"\s*\([^)]*\)\s*$", "", suffix.replace("_", " ")).strip()
            if label and re.search(r"[A-Za-z]", label):
                members.append(label)
        unique = list(dict.fromkeys(members))
        return unique if len(unique) > 1 or any(urls) else []

    def register_table_structure(
        self, table_name: str, rows: list[dict], *, row_indices: list[int] | None = None,
        cell_links: list[dict] | None = None,
    ) -> None:
        """Record Table/Row/Column/Cell structure in the provenance trace."""
        table_id = f"table:{table_name}"
        self.structural_nodes.setdefault(table_id, {"id": table_id, "type": "Table", "label": table_name})
        links_by_cell: dict[tuple[str, str, str], list[str]] = {}
        for link in cell_links or []:
            key = (
                str(link.get("row_index")),
                str(link.get("column_name", "")),
                str(link.get("cell_value", "")),
            )
            links_by_cell.setdefault(key, []).append(str(link.get("url", "")))

        for selected_index, row in enumerate(rows):
            row_index = (
                row_indices[selected_index]
                if row_indices is not None and selected_index < len(row_indices)
                else selected_index
            )
            row_id = f"{table_id}:row:{row_index}"
            self.structural_nodes[row_id] = {"id": row_id, "type": "Row", "row_index": row_index}
            self.structural_edges.append({"head": table_id, "relation": "row_contains", "tail": row_id})
            cells = list(row.items())
            subject = next(
                (str(value) for _, value in cells if str(value).strip()), row_id
            )
            self.record_edges.append({
                "head": subject,
                "relation": "has_record",
                "tail": row_id,
                "source_type": "table",
                "source_id": table_name,
                "row_index": row_index,
                "column_name": cells[0][0] if cells else None,
                "header_path": (str(cells[0][0]),) if cells else None,
                "structural": True,
            })
            for cell_index, (column, value) in enumerate(cells):
                column_id = f"{table_id}:column:{column}"
                cell_id = f"{row_id}:cell:{column}"
                self.structural_nodes.setdefault(column_id, {"id": column_id, "type": "Column", "label": str(column)})
                self.structural_nodes[cell_id] = {
                    "id": cell_id, "type": "Cell", "value": str(value),
                    "row_index": row_index, "column": str(column),
                }
                self.structural_edges.extend((
                    {"head": row_id, "relation": "row_contains", "tail": cell_id},
                    {"head": cell_id, "relation": "column_of", "tail": column_id},
                ))
                if cell_index > 0 and str(value).strip():
                    self.record_edges.append({
                        "head": row_id,
                        "relation": self.normalize_relation(str(column)),
                        "tail": str(value),
                        "source_type": "table",
                        "source_id": table_name,
                        "row_index": row_index,
                        "column_name": str(column),
                        "header_path": tuple(
                            part for part in str(column).replace("__", "_").split("_")
                            if part
                        ),
                        "structural": True,
                    })
                    for member in self.split_cell_entities(
                        str(value),
                        links_by_cell.get((str(row_index), str(column), str(value)), []),
                    ):
                        if member == str(value):
                            continue
                        self.record_edges.append({
                            "head": row_id,
                            "relation": self.normalize_relation(str(column)),
                            "tail": member,
                            "source_type": "table",
                            "source_id": table_name,
                            "row_index": row_index,
                            "column_name": str(column),
                            "header_path": (str(column),),
                            "structural": True,
                            "derived_from_cell_split": True,
                        })
        for link in cell_links or []:
            value, url = str(link.get("cell_value", "")), str(link.get("url", ""))
            if not value.strip() or not url.strip():
                continue
            row_index = link.get("row_index")
            column_name = link.get("column_name")
            passage_id = f"passage:{url}"
            self.structural_nodes.setdefault(passage_id, {
                "id": passage_id, "type": "PassageReference", "label": url,
            })
            self.structural_edges.append({
                "head": value, "relation": "linked_passage", "tail": passage_id,
            })
            self.record_edges.append({
                "head": value,
                "relation": "linked_passage",
                "tail": passage_id,
                "source_type": "table",
                "source_id": table_name,
                "row_index": row_index,
                "column_name": column_name,
                "header_path": (str(column_name),) if column_name else None,
                "structural": True,
            })
            for member in self.split_cell_entities(value, [url]):
                if member == value:
                    continue
                self.structural_edges.append({
                    "head": member, "relation": "linked_passage", "tail": passage_id,
                })
                self.record_edges.append({
                    "head": member,
                    "relation": "linked_passage",
                    "tail": passage_id,
                    "source_type": "table",
                    "source_id": table_name,
                    "row_index": row_index,
                    "column_name": column_name,
                    "header_path": (str(column_name),) if column_name else None,
                    "structural": True,
                    "derived_from_cell_split": True,
                })

    def register_passage(
        self, passage_id: str, text: str = "", *, context_before: str = "",
    ) -> None:
        context = {
            "source_id": str(passage_id),
            "text": str(text),
            "context_before": str(context_before),
        }
        self.text_contexts[str(passage_id)] = context
        node_id = f"passage:{passage_id}"
        self.structural_nodes[node_id] = {
            "id": node_id,
            "type": "Passage",
            "label": passage_id,
            "context": dict(context),
        }
        # A table cell can deterministically point to this source before the
        # passage is registered. Attach its text to that bridge so path-text
        # reasoning can read it without requiring a text-extraction LLM call.
        for record in self.record_edges:
            if (
                record.get("relation") == "linked_passage"
                and record.get("tail") == node_id
            ):
                record["contexts"] = [dict(context)]
        for _, _, data in self.graph.in_edges(str(passage_id), data=True):
            if data.get("relation") == "linked_passage":
                data["contexts"] = [dict(context)]

    def path_edge_records(self) -> list[dict]:
        """Return semantic and row-record edges for grounded text-path search."""
        records = []
        for index, (head, tail, key, data) in enumerate(
            self.graph.edges(keys=True, data=True)
        ):
            provenance = data["provenance"]
            records.append({
                "edge_id": f"semantic:{index}:{key}",
                "head": str(head),
                "relation": data["relation"],
                "tail": str(tail),
                "source_type": provenance.source_type,
                "source_id": provenance.source_id,
                "row_index": provenance.row_index,
                "column_name": provenance.column_name,
                "header_path": provenance.header_path,
                "structural": False,
                "contexts": [dict(item) for item in data.get("contexts", [])],
            })
        for index, record in enumerate(self.record_edges):
            records.append({"edge_id": f"record:{index}", **record})
        return records

    @staticmethod
    def normalize_relation(relation: str) -> str:
        return normalize_relation(relation)

    def merge_entities(
        self, canonical: str, aliases: list[str], *, tier: str = "manual", score: float = 1.0
    ) -> None:
        """Gộp các node trùng thực thể (do entity resolution) về 1 tên canonical."""
        for alias in aliases:
            if alias == canonical or alias not in self.graph:
                continue
            self.graph.add_node(canonical)
            for _, tgt, data in list(self.graph.out_edges(alias, data=True)):
                self.graph.add_edge(canonical, tgt, **data)
            for src, _, data in list(self.graph.in_edges(alias, data=True)):
                self.graph.add_edge(src, canonical, **data)
            for context in self.node_contexts.pop(str(alias), []):
                self._add_node_context(str(canonical), context)
            if str(alias) in self.node_types:
                self.node_types.setdefault(str(canonical), set()).update(
                    self.node_types.pop(str(alias))
                )
            self.graph.remove_node(alias)
            self.entity_aliases[alias] = canonical
            for old_alias, target in list(self.entity_aliases.items()):
                if target == alias:
                    self.entity_aliases[old_alias] = canonical
            self.resolution_log.append(
                {"tier": tier, "alias": alias, "canonical": canonical, "score": round(score, 4)}
            )

    def _resolve_entity(self, entity: str) -> str:
        seen = set()
        while entity in self.entity_aliases and entity not in seen:
            seen.add(entity)
            entity = self.entity_aliases[entity]
        if entity not in self.graph:
            key = normalize_key(entity)
            if key in self.entity_key_aliases:
                return self.entity_key_aliases[key]
            ontology_name = {
                normalize_key(alias): canonical for alias, canonical in self.entity_aliases.items()
            }.get(key)
            if ontology_name:
                return ontology_name
            for node in self.graph.nodes():
                if normalize_key(node) == key:
                    return node
        return entity

    # ---- API an toàn cấp cho code do LLM sinh (dùng trong sandbox) ----
    def get_neighbors(self, entity: str, relation: Optional[str] = None) -> list[str]:
        entity = self._resolve_entity(entity)
        if entity not in self.graph:
            return []
        out = []
        seen = set()
        normalized = self.normalize_relation(relation) if relation is not None else None
        for _, tgt, data in self.graph.out_edges(entity, data=True):
            if normalized is None or data.get("relation") == normalized:
                if tgt not in seen:
                    out.append(tgt)
                    seen.add(tgt)
        return out

    def get_sources(self, entity: str, relation: Optional[str] = None) -> list[str]:
        """Return heads of incoming edges whose tail is ``entity``."""
        entity = self._resolve_entity(entity)
        if entity not in self.graph:
            return []
        normalized = self.normalize_relation(relation) if relation is not None else None
        sources = []
        seen = set()
        for src, _, data in self.graph.in_edges(entity, data=True):
            if normalized is None or data.get("relation") == normalized:
                if src not in seen:
                    sources.append(src)
                    seen.add(src)
        return sources

    def get_relations(self, entity: str) -> list[str]:
        entity = self._resolve_entity(entity)
        if entity not in self.graph:
            return []
        return sorted({d["relation"] for _, _, d in self.graph.out_edges(entity, data=True)})

    def filter(self, entities: list[str], predicate: Callable[[str], bool]) -> list[str]:
        return [e for e in entities if predicate(e)]

    def get_provenance(self, head: str, tail: str) -> list[Provenance]:
        head, tail = self._resolve_entity(head), self._resolve_entity(tail)
        if not self.graph.has_edge(head, tail):
            return []
        return [d["provenance"] for d in self.graph.get_edge_data(head, tail).values()]

    def get_node_contexts(self, entity: str) -> list[dict]:
        """Return retrieved text passages that enriched a semantic node."""
        entity = self._resolve_entity(entity)
        return [dict(item) for item in self.node_contexts.get(str(entity), [])]

    def get_edge_contexts(
        self, head: str, tail: str, relation: Optional[str] = None,
    ) -> list[dict]:
        """Return deduplicated text contexts attached to matching graph edges."""
        head, tail = self._resolve_entity(head), self._resolve_entity(tail)
        if not self.graph.has_edge(head, tail):
            return []
        normalized = self.normalize_relation(relation) if relation is not None else None
        contexts = []
        seen = set()
        for data in self.graph.get_edge_data(head, tail).values():
            if normalized is not None and data.get("relation") != normalized:
                continue
            for context in data.get("contexts", []):
                key = (context.get("source_id"), context.get("text"))
                if key not in seen:
                    contexts.append(dict(context))
                    seen.add(key)
        return contexts

    def get_evidence(
        self, head: str, tail: str, relation: Optional[str] = None
    ) -> list[EvidenceRef]:
        """Return verified evidence records for matching graph edges."""
        head, tail = self._resolve_entity(head), self._resolve_entity(tail)
        if not self.graph.has_edge(head, tail):
            return []
        normalized = self.normalize_relation(relation) if relation is not None else None
        evidence = []
        for data in self.graph.get_edge_data(head, tail).values():
            if normalized is not None and data.get("relation") != normalized:
                continue
            provenance = data["provenance"]
            edge_contexts = data.get("contexts", [])
            evidence.append(EvidenceRef(
                head=head,
                relation=data["relation"],
                tail=tail,
                source_type=provenance.source_type,
                source_id=provenance.source_id,
                source_group=provenance.source_group,
                domain=provenance.domain,
                row_index=provenance.row_index,
                column_name=provenance.column_name,
                header_path=provenance.header_path,
                text_context=(
                    str(edge_contexts[0].get("text", ""))
                    if edge_contexts else None
                ),
                derived_from_compound=provenance.derived_from_compound,
            ))
        return evidence

    def is_empty(self) -> bool:
        return self.graph.number_of_nodes() == 0

    def summary(self) -> dict:
        resolution_counts: dict[str, int] = {}
        for event in self.resolution_log:
            tier = event["tier"]
            resolution_counts[tier] = resolution_counts.get(tier, 0) + 1
        return {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "num_record_edges": len(self.record_edges),
            "num_text_contexts": len(self.text_contexts),
            "num_contextualized_nodes": sum(
                bool(value) for value in self.node_contexts.values()
            ),
            "num_contextualized_edges": sum(
                bool(data.get("contexts")) for _, _, data in self.graph.edges(data=True)
            ),
            "relations": sorted({d["relation"] for _, _, d in self.graph.edges(data=True)}),
            "num_entity_aliases": len(self.entity_aliases),
            "entity_resolution": resolution_counts,
            "num_rejected_triples": len(self.rejection_log),
            "num_extraction_errors": len(self.extraction_errors),
            "node_types": {key: sorted(value) for key, value in self.node_types.items()},
        }

    def to_trace(self) -> dict:
        """Serialize the complete per-question KG for audit and visualization."""
        edges = []
        for head, tail, key, data in self.graph.edges(keys=True, data=True):
            provenance = data["provenance"]
            edges.append({
                "edge_id": str(key),
                "head": head,
                "relation": data["relation"],
                "tail": tail,
                "provenance": {
                    "source_type": provenance.source_type,
                    "source_id": provenance.source_id,
                    "raw_snippet": provenance.raw_snippet,
                    "source_group": provenance.source_group,
                    "domain": provenance.domain,
                    "row_index": provenance.row_index,
                    "column_name": provenance.column_name,
                    "header_path": provenance.header_path,
                    "derived_from_compound": provenance.derived_from_compound,
                },
                "contexts": [dict(item) for item in data.get("contexts", [])],
            })
        return {
            # Keep the legacy string list for renderers and downstream scripts;
            # typed metadata is supplied separately.
            "nodes": [str(node) for node in self.graph.nodes()],
            "node_metadata": [
                {
                    "id": str(node),
                    "types": sorted(self.node_types.get(str(node), {"Entity"})),
                    "contexts": [
                        dict(item) for item in self.node_contexts.get(str(node), [])
                    ],
                }
                for node in self.graph.nodes()
            ],
            "edges": edges,
            "structural_nodes": list(self.structural_nodes.values()),
            "structural_edges": list(self.structural_edges),
            "record_edges": list(self.record_edges),
            "text_contexts": dict(self.text_contexts),
            "aliases": dict(self.entity_aliases),
            "resolution_log": list(self.resolution_log),
            "rejection_log": list(self.rejection_log),
            "extraction_errors": list(self.extraction_errors),
            "summary": self.summary(),
        }
