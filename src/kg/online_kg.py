"""KG tạm dựng per-query (online/on-the-fly), khác với Hydra gốc (dùng Freebase/Wikidata offline).

API public trên đối tượng này chính là những gì code do LLM sinh ra được phép gọi
trong SandboxExecutor -- xem src/execution/sandbox.py.
"""

from __future__ import annotations

from typing import Callable, Optional

import networkx as nx

from src.kg.schema import Triple, Provenance


class OnlineKG:
    def __init__(self):
        self.graph = nx.MultiDiGraph()

    # ---- xây dựng ----
    def add_triple(self, triple: Triple) -> None:
        self.graph.add_node(triple.head)
        self.graph.add_node(triple.tail)
        self.graph.add_edge(
            triple.head, triple.tail,
            relation=triple.relation,
            provenance=triple.provenance,
        )

    def merge_entities(self, canonical: str, aliases: list[str]) -> None:
        """Gộp các node trùng thực thể (do entity resolution) về 1 tên canonical."""
        for alias in aliases:
            if alias == canonical or alias not in self.graph:
                continue
            for _, tgt, data in list(self.graph.out_edges(alias, data=True)):
                self.graph.add_edge(canonical, tgt, **data)
            for src, _, data in list(self.graph.in_edges(alias, data=True)):
                self.graph.add_edge(src, canonical, **data)
            self.graph.remove_node(alias)

    # ---- API an toàn cấp cho code do LLM sinh (dùng trong sandbox) ----
    def get_neighbors(self, entity: str, relation: Optional[str] = None) -> list[str]:
        if entity not in self.graph:
            return []
        out = []
        for _, tgt, data in self.graph.out_edges(entity, data=True):
            if relation is None or data.get("relation") == relation:
                out.append(tgt)
        return out

    def get_relations(self, entity: str) -> list[str]:
        if entity not in self.graph:
            return []
        return sorted({d["relation"] for _, _, d in self.graph.out_edges(entity, data=True)})

    def filter(self, entities: list[str], predicate: Callable[[str], bool]) -> list[str]:
        return [e for e in entities if predicate(e)]

    def get_provenance(self, head: str, tail: str) -> list[Provenance]:
        if not self.graph.has_edge(head, tail):
            return []
        return [d["provenance"] for d in self.graph.get_edge_data(head, tail).values()]

    def is_empty(self) -> bool:
        return self.graph.number_of_nodes() == 0

    def summary(self) -> dict:
        return {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "relations": sorted({d["relation"] for _, _, d in self.graph.edges(data=True)}),
        }
