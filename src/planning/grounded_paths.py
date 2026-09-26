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


def _edge_evidence_types(edge: dict) -> set[str]:
    """Include passage context as text evidence even on a table hyperlink."""
    kinds = {str(edge.get("source_type", ""))}
    if any(str(context.get("text", "")).strip() for context in edge.get("contexts", [])):
        kinds.add("text")
    return kinds - {""}


def _compact_digits(value: str) -> str:
    return re.sub(r"\D", "", str(value))


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


    @staticmethod
    def _path_constraints(question: str, records: list[dict]) -> dict:
        """Find question literals that are actually evidenced in this KG."""
        rendered = [f"{edge['head']} {edge['relation']} {edge['tail']} {_context_text(edge)}" for edge in records]
        numeric = tuple(
            literal for literal in re.findall(r"(?<!\d)\d[\d,]*(?:\.\d+)?", question)
            if any(_compact_digits(literal) in _compact_digits(text) for text in rendered)
        )
        text_term_sources: dict[str, set[str]] = defaultdict(set)
        for edge in records:
            for context in edge.get("contexts", []):
                source_id = str(context.get("source_id", edge.get("source_id", "")))
                for term in _terms(f"{context.get('context_before', '')} {context.get('text', '')}"):
                    text_term_sources[term].add(source_id)
        ignored = {"what", "which", "where", "when", "who", "whose", "how", "team", "club", "stadium", "republic"}
        keywords = tuple(
            term.casefold() for term in re.findall(r"\b[A-Z][A-Za-z'-]{3,}\b", question)
            if term.casefold() not in ignored and len(text_term_sources.get(term.casefold(), set())) == 1
        )

        team_entities = {
            normalize_key(edge["head"])
            for edge in records
            if edge.get("relation") == "has_record"
            and re.search(r"\b(team|club)\b", str(edge.get("column_name", "")), re.I)
        }
        row_link_counts: dict[tuple[str, int], set[str]] = defaultdict(set)
        for edge in records:
            if edge.get("relation") == "linked_passage" and edge.get("row_index") is not None \
                    and re.search(r"ground|stadium|venue|home", str(edge.get("column_name", "")), re.I):
                key = (str(edge.get("source_id")), int(edge["row_index"]))
                row_link_counts[key].add(normalize_key(str(edge.get("tail", "")).removeprefix("passage:")))

        return {
            "numeric": tuple(dict.fromkeys(numeric)),
            "keywords": tuple(dict.fromkeys(keywords)),
            "requires_team_or_club": bool(re.search(r"\bwho\s+plays\b", question, re.I)),
            "team_entities": team_entities,
            "single_venue_question": bool(re.search(r"\bthe\s+stadium\b", question, re.I)),
            "row_link_counts": {key: len(value) for key, value in row_link_counts.items()},
        }

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
        witness_seeds = []
        for witness in (constraint_context or {}).get("table_witnesses", []):
            for entity in witness.get("bridge_entities", ()):
                if entity:
                    witness_seeds.append(str(entity))
            for link in witness.get("hyperlinks", ()):
                if link:
                    witness_seeds.append(f"passage:{link}")
                    witness_seeds.append(str(link))

        seeds = [node for node in dict.fromkeys(witness_seeds) if node in nodes]
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
                if node not in seeds:
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
        source_types = set().union(*(_edge_evidence_types(edge) for edge in edges))
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
        scoring = (constraint_context or {}).get("_path_scoring", {})
        path_text = " ".join(
            f"{edge['head']} {edge['relation']} {edge['tail']} {_context_text(edge)}"
            for edge in edges
        )
        numeric = tuple(scoring.get("numeric", ()))
        numeric_hit = sum(_compact_digits(value) in _compact_digits(path_text) for value in numeric)
        numeric_score = 4.0 * numeric_hit - 3.0 * (len(numeric) - numeric_hit)
        keywords = set(scoring.get("keywords", ()))
        keyword_hit = len(keywords & _terms(path_text))
        keyword_score = 2.5 * keyword_hit - 1.5 * (len(keywords) - keyword_hit)
        linked_with_context = [
            edge for edge in edges
            if edge.get("relation") == "linked_passage" and edge.get("contexts")
        ]
        bridge_bonus = (
            2.0 if linked_with_context and any(edge.get("row_index") is not None for edge in edges)
            else 0.0
        )
        team_score = 0.0
        if scoring.get("requires_team_or_club"):
            team_score = 2.0 if path_keys & set(scoring.get("team_entities", ())) else -2.0
        venue_score = 0.0
        if scoring.get("single_venue_question"):
            row_counts = scoring.get("row_link_counts", {})
            path_rows = {(str(edge.get("source_id")), int(edge["row_index"])) for edge in edges if edge.get("row_index") is not None}
            if path_rows:
                linked_count = min(row_counts.get(row, 99) for row in path_rows)
                venue_score = 2.5 if linked_count <= 1 else -0.5 * (linked_count - 1)

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
        table_witnesses = (constraint_context or {}).get("table_witnesses", [])
        witness_bonus = 0.0
        is_witness_grounded = False
        for witness in table_witnesses:
            w_rows = set(witness.get("row_indices", ()))
            w_links = {
                str(link).removeprefix("/wiki/").removeprefix("passage:").casefold()
                for link in witness.get("hyperlinks", ())
            }
            w_entities = {normalize_key(str(e)) for e in witness.get("bridge_entities", ())}
            path_rows = {edge.get("row_index") for edge in edges if edge.get("row_index") is not None}
            path_nodes_norm = {normalize_key(node) for node in nodes}
            touches_row = bool(w_rows & path_rows)
            touches_link = any(
                any(w_link in str(edge.get("tail", "")).casefold() or w_link in str(edge.get("head", "")).casefold() for w_link in w_links)
                for edge in edges
            )
            touches_entity = bool(w_entities & path_nodes_norm)
            if touches_row and (touches_link or touches_entity):
                witness_bonus = max(witness_bonus, 8.0)
                is_witness_grounded = True
            elif touches_row or touches_link:
                witness_bonus = max(witness_bonus, 5.0)
                is_witness_grounded = True

        if is_witness_grounded and numeric_score < 0:
            numeric_score = 0.0

        length_penalty = 0.35 * max(len(edges) - 1, 0)
        components = {
            "grounded_edges": 1.0,
            "query_entity_match": round(query_entity, 4),
            "relation_match": round(relation_match, 4),
            "text_context_match": round(text_context_match, 4),
            "query_coverage": round(coverage, 4),
            "single_venue_specificity": venue_score,
            "constraint_coverage": constraint_coverage,
            "cross_modal_completeness": cross_modal,
            "row_context": row_context,
            "row_entity_binding": row_entity_binding,
            "numeric_literal_coverage": numeric_score,
            "strong_keyword_coverage": keyword_score,
            "hyperlink_passage_bridge": bridge_bonus,
            "table_witness_match": witness_bonus,
            "answer_type_path_filter": team_score,
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
        scoring_context = {**(constraint_context or {}), "_path_scoring": self._path_constraints(question, records)}


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
            bridged_attributes = [
                (attribute, link)
                for attribute in attributes
                for link in records
                if link.get("relation") == "linked_passage"
                and normalize_key(link["head"]) == normalize_key(attribute["tail"])
            ]
            bridged_attributes.sort(
                key=lambda pair: (bool(pair[1].get("contexts")), str(pair[1].get("tail", "")).startswith("passage:")),
                reverse=True,
            )
            if bridged_attributes and self.max_hops >= 3:
                attribute, link = bridged_attributes[0]
                bundle = [record_link, attribute, link]
            else:
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
                question, nodes, traversed, scoring_context, fact_sources,
            ))
            if bridged_attributes and self.max_hops >= 3:
                for target in attributes:
                    if target is attribute:
                        continue
                    answer_traversed = [
                        self._traversal(link, str(link["tail"]), str(link["head"])),
                        self._traversal(attribute, str(attribute["tail"]), str(attribute["head"])),
                        self._traversal(target, str(target["head"]), str(target["tail"])),
                    ]
                    answer_nodes = list(dict.fromkeys(
                        value for edge in answer_traversed
                        for value in (edge["traversal_from"], edge["traversal_to"])
                    ))
                    raw_paths.append(self._make_path(
                        f"row_bridge_{record_link.get('row_index')}_{len(raw_paths) + 1}",
                        question, answer_nodes, answer_traversed,
                        scoring_context, fact_sources,
                    ))


        seeds = self._seeds(question, records, scoring_context)
        enumerated = 0
        for seed in seeds:
            stack = [(seed, [seed], [], set())]
            while stack and enumerated < self.max_enumerated:
                current, nodes, edges, used = stack.pop()
                if edges:
                    raw_paths.append(self._make_path(
                        f"grounded_{len(raw_paths) + 1}",
                        question, nodes, edges, scoring_context, fact_sources,
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
        if scoring_context["_path_scoring"].get("requires_team_or_club"):
            typed = [
                path for path in raw_paths
                if path.score_components.get("answer_type_path_filter", 0.0) >= 0
            ]
            if typed:
                raw_paths = typed

        table_witnesses = scoring_context.get("table_witnesses", [])
        reserved_witness_paths: list[ReasoningPath] = []
        for witness in table_witnesses:
            w_paths = [
                path for path in raw_paths
                if path.score_components.get("table_witness_match", 0.0) >= 5.0
            ]
            if w_paths:
                best_w = max(w_paths, key=lambda p: (p.score, -len(p.edges)))
                if best_w not in reserved_witness_paths:
                    reserved_witness_paths.append(best_w)

        selected, seen = [], set()
        for path in reserved_witness_paths:
            signature = tuple(
                (edge["edge_id"], edge["direction"]) for edge in path.edges
            )
            if signature not in seen:
                seen.add(signature)
                selected.append(path)

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

        if selected:
            def evidence_strength(path: ReasoningPath) -> float:
                components = path.score_components
                return sum(components.get(name, 0.0) for name in (
                    "numeric_literal_coverage", "strong_keyword_coverage",
                    "hyperlink_passage_bridge",
                ))

            best_selected_strength = max(evidence_strength(path) for path in selected)
            for candidate in raw_paths:
                if candidate in selected:
                    continue
                candidate_strength = evidence_strength(candidate)
                has_text = any("text" in _edge_evidence_types(edge) for edge in candidate.edges)
                if (
                    has_text
                    and candidate.score >= selected[-1].score - 2.0
                    and candidate_strength > best_selected_strength
                ):
                    selected[-1] = candidate
                    selected.sort(key=lambda path: (-path.score, len(path.edges), path.path_id))
                    break
        return selected
