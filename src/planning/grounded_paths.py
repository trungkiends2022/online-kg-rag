"""Deterministic, edge-grounded path generation for the path-text method."""

from __future__ import annotations

import re
from collections import defaultdict

from src.kg.normalization import normalize_key
from src.kg.online_kg import OnlineKG
from src.planning.planner import PathStep, ReasoningPath


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "had", "has", "have", "how", "in", "is", "it", "of", "on",
    "or", "the", "to", "was", "were", "what", "when", "which", "who", "whose",
    "with",
}


def _terms(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", normalize_key(value))
        if len(token) > 1 and token not in _STOPWORDS
    }


def _context_text(edge: dict) -> str:
    return " ".join(
        str(context.get(field, ""))
        for context in edge.get("contexts", [])
        for field in ("context_before", "text")
    )


class GroundedPathPlanner:
    """Enumerate short connected evidence paths and score their text forms."""

    def __init__(
        self,
        *,
        max_hops: int = 3,
        max_branching: int = 20,
        max_enumerated: int = 4000,
    ):
        self.max_hops = max_hops
        self.max_branching = max_branching
        self.max_enumerated = max_enumerated
        self.last_error: str | None = None

    @staticmethod
    def _constraint_values(context: dict | None) -> set[str]:
        values = set()
        trace = context or {}
        for constraint in trace.get("table_constraints", []):
            values.update(str(value) for value in constraint.get("candidates", ()))
            if constraint.get("value") is not None:
                values.add(str(constraint["value"]))
        values.update(
            str(value)
            for value in trace.get("constraint_policy", {}).get(
                "allowed_output_values", ()
            )
        )
        values.update(
            str(value)
            for value in trace.get("entity_anchor", {}).get("bridge_entities", ())
        )
        return {normalize_key(value) for value in values if value.strip()}

    def _seeds(
        self,
        question: str,
        records: list[dict],
        constraint_context: dict | None,
    ) -> list[str]:
        question_key = normalize_key(question)
        question_terms = _terms(question)
        constrained = self._constraint_values(constraint_context)
        nodes = list(dict.fromkeys(
            str(value)
            for edge in records
            for value in (edge["head"], edge["tail"])
        ))
        seeds = []
        for node in nodes:
            if node.startswith("table:") and ":row:" in node:
                continue
            key = normalize_key(node)
            terms = _terms(node)
            if (
                key in constrained
                or (len(key) >= 2 and key in question_key)
                or len(terms & question_terms) >= 2
            ):
                seeds.append(node)
        if seeds:
            return seeds[:30]

        edge_rank = sorted(
            records,
            key=lambda edge: len(
                _terms(f'{edge["relation"]} {_context_text(edge)}') & question_terms
            ),
            reverse=True,
        )
        for edge in edge_rank:
            if _terms(f'{edge["relation"]} {_context_text(edge)}') & question_terms:
                seeds.extend((str(edge["head"]), str(edge["tail"])))
            if len(seeds) >= 20:
                break
        return list(dict.fromkeys(seeds))

    @staticmethod
    def _traversal(edge: dict, current: str, target: str) -> dict:
        direction = (
            "forward"
            if current == str(edge["head"]) and target == str(edge["tail"])
            else "reverse"
        )
        return {
            **edge,
            "traversal_from": current,
            "traversal_to": target,
            "direction": direction,
        }

    @staticmethod
    def _goal(edge: dict) -> str:
        goal = f'{edge["head"]} --{edge["relation"]}--> {edge["tail"]}'
        if edge.get("direction") == "reverse":
            goal += " [traverse reverse]"
        return goal

    def _score(
        self,
        question: str,
        nodes: list[str],
        edges: list[dict],
        constraint_context: dict | None,
        fact_sources: dict[tuple[str, str, str], set[str]],
    ) -> tuple[float, dict[str, float]]:
        question_terms = _terms(question)
        node_terms = _terms(" ".join(nodes))
        relation_terms = _terms(" ".join(str(edge["relation"]) for edge in edges))
        context_terms = _terms(" ".join(_context_text(edge) for edge in edges))
        rendered_terms = node_terms | relation_terms | context_terms
        query_entity = 2.0 * min(
            len(node_terms & question_terms) / max(min(len(question_terms), 4), 1),
            1.0,
        )
        relation_match = 2.0 * min(
            len(relation_terms & question_terms) / max(min(len(question_terms), 3), 1),
            1.0,
        )
        text_context_match = min(
            len(context_terms & question_terms) / max(min(len(question_terms), 4), 1),
            1.0,
        )
        coverage = 2.0 * len(rendered_terms & question_terms) / max(
            len(question_terms), 1
        )
        constrained = self._constraint_values(constraint_context)
        path_keys = {normalize_key(node) for node in nodes}
        constraint_coverage = 2.0 if constrained & path_keys else 0.0
        source_types = {str(edge.get("source_type")) for edge in edges}
        cross_modal = 1.5 if {"table", "text"} <= source_types else 0.0
        rows = {
            (edge.get("source_id"), edge.get("row_index"))
            for edge in edges
            if edge.get("row_index") is not None
        }
        record_edges = sum(bool(edge.get("structural")) for edge in edges)
        row_context = 1.0 if record_edges >= 2 and len(rows) == 1 else 0.0
        row_entity_binding = (
            1.0
            if row_context and any(edge["relation"] == "has_record" for edge in edges)
            else 0.0
        )
        corroboration = 0.0
        for edge in edges:
            fact = (
                normalize_key(edge["head"]),
                normalize_key(edge["relation"]),
                normalize_key(edge["tail"]),
            )
            if {"table", "text"} <= fact_sources.get(fact, set()):
                corroboration = 1.0
                break
        length_penalty = 0.35 * max(len(edges) - 1, 0)
        components = {
            "grounded_edges": 1.0,
            "query_entity_match": round(query_entity, 4),
            "relation_match": round(relation_match, 4),
            "text_context_match": round(text_context_match, 4),
            "query_coverage": round(coverage, 4),
            "constraint_coverage": constraint_coverage,
            "cross_modal_completeness": cross_modal,
            "row_context": row_context,
            "row_entity_binding": row_entity_binding,
            "same_fact_corroboration": corroboration,
            "length_penalty": round(length_penalty, 4),
        }
        score = sum(
            value for name, value in components.items() if name != "length_penalty"
        ) - length_penalty
        return round(score, 4), components

    def _make_path(
        self,
        path_id: str,
        question: str,
        nodes: list[str],
        edges: list[dict],
        constraint_context: dict | None,
        fact_sources: dict[tuple[str, str, str], set[str]],
    ) -> ReasoningPath:
        score, components = self._score(
            question, nodes, edges, constraint_context, fact_sources
        )
        return ReasoningPath(
            path_id=path_id,
            steps=[
                PathStep(index + 1, self._goal(edge), index or None)
                for index, edge in enumerate(edges)
            ],
            nodes=nodes,
            edges=edges,
            score=score,
            score_components=components,
        )

    def generate_candidates(
        self,
        question: str,
        kg: OnlineKG,
        n: int = 5,
        constraint_context: dict | None = None,
    ) -> list[ReasoningPath]:
        self.last_error = None
        if n < 1:
            return []
        records = kg.path_edge_records()
        if not records:
            return []

        fact_sources: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        adjacency: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for edge in records:
            fact = (
                normalize_key(edge["head"]),
                normalize_key(edge["relation"]),
                normalize_key(edge["tail"]),
            )
            fact_sources[fact].add(str(edge.get("source_type")))
            head, tail = str(edge["head"]), str(edge["tail"])
            adjacency[head].append((tail, edge))
            adjacency[tail].append((head, edge))

        question_terms = _terms(question)
        for node, neighbors in adjacency.items():
            neighbors.sort(
                key=lambda item: (
                    len(
                        (
                            _terms(item[1]["relation"])
                            | _terms(item[0])
                            | _terms(_context_text(item[1]))
                        )
                        & question_terms
                    ),
                    bool(item[1].get("structural")),
                ),
                reverse=True,
            )
            adjacency[node] = neighbors[: self.max_branching]

        raw_paths: list[ReasoningPath] = []
        # A row bundle represents a connected evidence subgraph, not a forced
        # linear chain. This keeps year/value/entity cells bound to one record.
        record_links = [edge for edge in records if edge["relation"] == "has_record"]
        for record_link in record_links:
            row_id = str(record_link["tail"])
            attributes = [
                edge for edge in records
                if str(edge["head"]) == row_id and edge.get("structural")
            ]
            attributes.sort(
                key=lambda edge: len(
                    (_terms(edge["relation"]) | _terms(edge["tail"])) & question_terms
                ),
                reverse=True,
            )
            bundle = [record_link, *attributes[: max(self.max_hops - 1, 1)]]
            traversed = [
                self._traversal(edge, str(edge["head"]), str(edge["tail"]))
                for edge in bundle
            ]
            nodes = list(dict.fromkeys(
                value for edge in traversed
                for value in (edge["traversal_from"], edge["traversal_to"])
            ))
            raw_paths.append(self._make_path(
                f"row_{record_link.get('row_index')}_{len(raw_paths) + 1}",
                question, nodes, traversed, constraint_context, fact_sources,
            ))

        seeds = self._seeds(question, records, constraint_context)
        enumerated = 0
        for seed in seeds:
            stack = [(seed, [seed], [], set())]
            while stack and enumerated < self.max_enumerated:
                current, nodes, edges, used = stack.pop()
                if edges:
                    raw_paths.append(self._make_path(
                        f"grounded_{len(raw_paths) + 1}",
                        question, nodes, edges, constraint_context, fact_sources,
                    ))
                    enumerated += 1
                if len(edges) >= self.max_hops:
                    continue
                for target, raw_edge in reversed(adjacency.get(current, [])):
                    edge_id = str(raw_edge["edge_id"])
                    if edge_id in used or target in nodes:
                        continue
                    stack.append((
                        target,
                        [*nodes, target],
                        [*edges, self._traversal(raw_edge, current, target)],
                        {*used, edge_id},
                    ))

        raw_paths.sort(key=lambda path: (-path.score, len(path.edges), path.path_id))
        selected, seen = [], set()
        for path in raw_paths:
            signature = tuple(
                (edge["edge_id"], edge["direction"]) for edge in path.edges
            )
            if signature in seen:
                continue
            seen.add(signature)
            selected.append(path)
            if len(selected) >= n:
                break
        return selected
