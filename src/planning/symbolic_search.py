"""Question-anchored bounded graph search used when generated programs dead-end."""

from __future__ import annotations

import re

import networkx as nx

from src.execution.sandbox import ExecResult
from src.kg.normalization import normalize_key
from src.kg.online_kg import OnlineKG
from src.planning.planner import PathStep, ReasoningPath


_STOPWORDS = {
    "a", "an", "and", "in", "is", "of", "the", "to", "was", "what", "which",
    "who", "whose", "with", "his", "her", "their",
}
_ANCHOR_GENERIC = {
    "career", "city", "country", "first", "most", "player", "populous",
    "season", "seasons", "seven", "world",
}


class SymbolicPathSearcher:
    """Find short, fully evidenced paths from question entities to target relations."""

    def __init__(self, max_hops: int = 4, max_candidates: int = 5):
        self.max_hops = max_hops
        self.max_candidates = max_candidates

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", normalize_key(text))
            if len(token) > 1 and token not in _STOPWORDS
        }

    @staticmethod
    def _looks_literal(value: str) -> bool:
        key = normalize_key(value)
        months = (
            "january|february|march|april|may|june|july|august|september|"
            "october|november|december"
        )
        return bool(re.fullmatch(r"[\d\s:./,%$-]+", str(value).strip())) or bool(
            re.search(rf"\b(?:{months})\b", key)
        )

    def search(self, question: str, kg: OnlineKG):
        question_key = normalize_key(question)
        question_terms = self._terms(question)
        anchors = []
        for node in kg.graph.nodes:
            node_key = normalize_key(str(node))
            node_terms = self._terms(str(node))
            distinctive = node_terms - _ANCHOR_GENERIC
            overlap = distinctive & (question_terms - _ANCHOR_GENERIC)
            exact_phrase = len(node_key) >= 3 and node_key in question_key
            fuzzy_phrase = (
                len(overlap) >= 2
                and len(distinctive) <= 8
            )
            if (exact_phrase and overlap) or fuzzy_phrase:
                anchors.append(node)
        if not anchors:
            return []

        relation_scores = {}
        for _, _, data in kg.graph.edges(data=True):
            relation = data.get("relation", "")
            terms = self._terms(relation)
            overlap = len(terms & question_terms)
            if overlap:
                phrase = " ".join(re.findall(r"[a-z0-9]+", relation.lower()))
                phrase_bonus = 1.0 if phrase and phrase in question_key else 0.0
                relation_scores[relation] = max(
                    relation_scores.get(relation, 0.0),
                    overlap / max(len(terms), 1) + phrase_bonus,
                )

        # Prefer relations explicitly described by at least two question words;
        # a one-word relation is accepted only when it matches completely.
        targets = {
            relation for relation, score in relation_scores.items()
            if score >= 1.0 or len(self._terms(relation) & question_terms) >= 2
        }
        if targets:
            best_relation_score = max(relation_scores[relation] for relation in targets)
            targets = {
                relation for relation in targets
                if relation_scores[relation] == best_relation_score
            }
        undirected = nx.Graph(kg.graph)
        found = []
        seen = set()
        for head, tail, data in kg.graph.edges(data=True):
            relation = data.get("relation", "")
            if relation not in targets:
                continue
            # Relations with an entity-valued semantic type must not terminate
            # in a date/number accidentally extracted from the same passage.
            if self._terms(relation) & {"city", "country", "person", "player", "club"}:
                if self._looks_literal(str(tail)):
                    continue
            for anchor in anchors:
                try:
                    prefix = nx.shortest_path(undirected, anchor, head)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                nodes = prefix + [tail]
                if len(nodes) - 1 > self.max_hops:
                    continue
                signature = (tuple(nodes), relation)
                if signature in seen:
                    continue
                seen.add(signature)
                evidence = []
                goals = []
                for left, right in zip(nodes, nodes[1:]):
                    forward = kg.get_evidence(left, right)
                    backward = kg.get_evidence(right, left)
                    edge_evidence = forward or backward
                    evidence.extend(edge_evidence)
                    if edge_evidence:
                        edge = edge_evidence[0]
                        goals.append(f"{edge.head} --{edge.relation}--> {edge.tail}")
                if not evidence:
                    continue
                path = ReasoningPath(
                    path_id=f"symbolic_{len(found) + 1}",
                    steps=[PathStep(i + 1, goal, i or None) for i, goal in enumerate(goals)],
                )
                result = ExecResult(
                    success=True,
                    value=tail,
                    evidence=tuple(dict.fromkeys(evidence)),
                    accessed_edges=len(evidence),
                )
                # More explicit relation matches and shorter anchored paths rank first.
                rank = (relation_scores[relation], -len(nodes), len(set(e.source_type for e in evidence)))
                found.append((rank, path, "# symbolic anchored graph search", result))

        found.sort(key=lambda item: item[0], reverse=True)
        return [(path, code, result) for _, path, code, result in found[: self.max_candidates]]
