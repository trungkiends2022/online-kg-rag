"""KG tạm dựng per-query (online/on-the-fly), khác với Hydra gốc (dùng Freebase/Wikidata offline).

API public trên đối tượng này chính là những gì code do LLM sinh ra được phép gọi
trong SandboxExecutor -- xem src/execution/sandbox.py.
"""

from __future__ import annotations

from typing import Callable, Optional

import networkx as nx

from src.kg.schema import Triple, Provenance
from src.kg.normalization import normalize_key, normalize_relation


class OnlineKG:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.entity_aliases: dict[str, str] = {}
        self.entity_key_aliases: dict[str, str] = {}
        self.resolution_log: list[dict] = []
        self.rejection_log: list[dict] = []

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
        self.graph.add_edge(
            triple.head, triple.tail,
            relation=self.normalize_relation(triple.relation),
            provenance=triple.provenance,
        )

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
        normalized = self.normalize_relation(relation) if relation is not None else None
        for _, tgt, data in self.graph.out_edges(entity, data=True):
            if normalized is None or data.get("relation") == normalized:
                out.append(tgt)
        return out

    def get_sources(self, entity: str, relation: Optional[str] = None) -> list[str]:
        """Return heads of incoming edges whose tail is ``entity``."""
        entity = self._resolve_entity(entity)
        if entity not in self.graph:
            return []
        normalized = self.normalize_relation(relation) if relation is not None else None
        sources = []
        for src, _, data in self.graph.in_edges(entity, data=True):
            if normalized is None or data.get("relation") == normalized:
                sources.append(src)
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
        }
