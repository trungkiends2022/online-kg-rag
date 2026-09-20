"""KG tạm dựng per-query (online/on-the-fly), khác với Hydra gốc (dùng Freebase/Wikidata offline).

API public trên đối tượng này chính là những gì code do LLM sinh ra được phép gọi
trong SandboxExecutor -- xem src/execution/sandbox.py.
"""

from __future__ import annotations

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
        self.structural_nodes: dict[str, dict] = {}
        self.structural_edges: list[dict] = []
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
        self.graph.add_edge(
            triple.head, triple.tail,
            relation=self.normalize_relation(triple.relation),
            provenance=triple.provenance,
        )

    def register_table_structure(self, table_name: str, rows: list[dict]) -> None:
        """Record Table/Row/Column/Cell structure in the provenance trace."""
        table_id = f"table:{table_name}"
        self.structural_nodes.setdefault(table_id, {"id": table_id, "type": "Table", "label": table_name})
        for row_index, row in enumerate(rows):
            row_id = f"{table_id}:row:{row_index}"
            self.structural_nodes[row_id] = {"id": row_id, "type": "Row", "row_index": row_index}
            self.structural_edges.append({"head": table_id, "relation": "row_contains", "tail": row_id})
            for column, value in row.items():
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

    def register_passage(self, passage_id: str) -> None:
        node_id = f"passage:{passage_id}"
        self.structural_nodes.setdefault(node_id, {"id": node_id, "type": "Passage", "label": passage_id})

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
                },
            })
        return {
            # Keep the legacy string list for renderers and downstream scripts;
            # typed metadata is supplied separately.
            "nodes": [str(node) for node in self.graph.nodes()],
            "node_metadata": [
                {"id": str(node), "types": sorted(self.node_types.get(str(node), {"Entity"}))}
                for node in self.graph.nodes()
            ],
            "edges": edges,
            "structural_nodes": list(self.structural_nodes.values()),
            "structural_edges": list(self.structural_edges),
            "aliases": dict(self.entity_aliases),
            "resolution_log": list(self.resolution_log),
            "rejection_log": list(self.rejection_log),
            "extraction_errors": list(self.extraction_errors),
            "summary": self.summary(),
        }
