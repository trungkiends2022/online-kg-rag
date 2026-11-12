"""Deterministic evidence-constrained answer recovery for OUEG/QEG traces.

ECAR is intentionally a post-reader executor.  It never reads a benchmark
label: candidates are table cells or graph nodes present in the retrieved
trace, and every returned candidate carries a bounded proof path.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import re
from typing import Any


_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "in", "is", "it", "of", "on", "or", "the", "that",
    "this", "to", "was", "what", "when", "where", "which", "who", "whose", "with",
})
_ORDINAL = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
_RELATION_CUES = frozenset({
    "address", "appointed", "area", "based", "became", "began", "born", "capital",
    "champion", "city", "closed", "country", "date", "debut", "debuted", "director",
    "dissolved", "elected", "ended", "established", "finish", "finished", "first", "founded",
    "formed", "home", "joined", "largest", "last", "latest", "launched",
    "located", "medal", "most", "name", "opened", "order", "owner", "played",
    "position", "premiered", "published", "rank", "ranked", "released", "retired",
    "season", "second", "seed", "standing", "third", "time", "title", "winner",
    "won", "wrote", "written", "year",
})

# Table schemas vary more than natural-language questions.  These aliases are
# intentionally checked against observed column/relation labels only; they do
# not invent a chronology or ranking where a row has no numeric witness.
_TEMPORAL_TERMS = frozenset({
    "appointed", "became", "began", "born", "closed", "date", "debut", "debuted",
    "dissolved", "elected", "ended", "established", "founded", "formed", "introduced", "joined",
    "launched", "opened", "premiered", "published", "released", "retired", "started",
    "year",
})
_RANK_RELATION = re.compile(r"rank|position|place|finish|standing|seed|order", re.I)


def _terms(value: object) -> set[str]:
    return {
        term for term in re.findall(r"[a-z0-9]+", str(value).casefold())
        if term not in _STOP
    }


def _normalise(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def _is_internal(value: object) -> bool:
    text = str(value or "").strip()
    return not text or text.startswith(("table:", "passage:")) or ":row:" in text or ":cell:" in text or ":column:" in text


def _target_type(question: str) -> str:
    text = question.casefold()
    if re.search(r"\b(how many|how much|number of|population|inhabitants?|count|portion|percent(?:age)?|ratio)\b", text):
        return "numeric"
    if re.search(r"\b(when|what year|which year|date)\b", text):
        return "temporal"
    if re.search(r"\b(where|which city|what city|which town|what town|largest city)\b", text):
        return "location"
    if re.search(r"\b(which|what|name of) (?:the )?(club|team)\b", text):
        return "club"
    if re.search(r"\b(who|which person|what person)\b", text):
        return "person"
    return "entity"


def _type_score(value: str, relation: str, target: str) -> float:
    text, rel = value.casefold(), relation.casefold()
    if target == "numeric":
        return 1.0 if re.fullmatch(r"[+-]?\d[\d,.%]*", text.strip()) else 0.0
    if target == "temporal":
        return 1.0 if re.search(r"\b(?:1[5-9]|20)\d{2}\b", text) else 0.0
    if target == "location":
        return 1.0 if re.search(r"city|town|location|located|based|country|province|state|region", rel) else 0.0
    if target == "club":
        return 1.0 if re.search(r"\b(club|fc|f\.c\.?|team|united)\b", text) else 0.0
    if target == "person":
        # Proper-name shape is only a weak positive; the proof path still
        # determines whether a candidate can replace a reader answer.
        return 0.5 if len(text.split()) >= 2 and not re.search(r"\d", text) else 0.0
    return 0.25


def _ordinal(question: str) -> int | None:
    lower = question.casefold()
    for word, value in _ORDINAL.items():
        if re.search(rf"\b{word}\b", lower):
            return value
    match = re.search(r"\b(\d+)(?:st|nd|rd|th)\b", lower)
    return int(match.group(1)) if match else None


def _query_constraints(question: str) -> dict[str, Any]:
    """Compile the answer-shaping constraints used by the proof validator."""
    terms = _terms(question)
    return {
        "answer_type": _target_type(question),
        "relation_cues": sorted(terms & _RELATION_CUES),
        "ordinal": _ordinal(question),
        "has_numeric_operator": bool(re.search(
            r"\b(how many|how much|number|population|portion|percent|ratio|most|least)\b",
            question, re.I,
        )),
    }


def _mention_variants(mention: str) -> set[str]:
    """Return label aliases mechanically derived from an evidence mention."""
    value = re.sub(r"\s+", " ", mention).strip(" ,.;:")
    variants = {value}
    without_trailing_linker = re.sub(r"\s+(?:of|the|and|in|on|for|to)$", "", value, flags=re.I).strip()
    if without_trailing_linker:
        variants.add(without_trailing_linker)
    without_parenthetical = re.sub(r"\s*\([^)]*\)", "", value).strip()
    if without_parenthetical:
        variants.add(without_parenthetical)
    without_article = re.sub(r"^(?:the|a|an)\s+", "", without_parenthetical, flags=re.I)
    if without_article:
        variants.add(without_article)
    without_admin_suffix = re.sub(
        r"\s+(?:province|district|county|city|state|region)$", "", without_article, flags=re.I,
    ).strip()
    if without_admin_suffix:
        variants.add(without_admin_suffix)
    historical_core = re.sub(
        r"\s+of\s+the\s+\d+(?:st|nd|rd|th)?\s+century$", "", without_article, flags=re.I,
    ).strip()
    if historical_core:
        variants.add(historical_core)
    number = re.match(r"^([+-]?\d[\d,.%]*)\b", without_article)
    if number:
        variants.add(number.group(1))
    return {item for item in variants if len(_normalise(item)) >= 2}


def _passage_mentions(text: str) -> set[str]:
    """Extract conservative surface candidates already present in a passage."""
    capitalized = re.findall(
        r"\b(?:[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’-]*)(?:\s+(?:[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’-]*|of|the|and|in|on|for|[0-9]{4})){0,5}",
        text,
    )
    counted = re.findall(r"\b[+-]?\d[\d,.%]*(?:\s+[a-z][a-z-]*){1,3}\b", text, flags=re.I)
    clock_times = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", text)
    mentions: set[str] = set()
    for raw in [*capitalized, *counted, *clock_times]:
        mentions.update(_mention_variants(raw))
    return mentions


@dataclass(frozen=True)
class _Edge:
    identifier: str
    head: str
    relation: str
    tail: str
    source_type: str


class EvidenceConstrainedAnswerRecovery:
    """Recover an answer denotation from an already retrieved heterogeneous graph.

    This deliberately implements a conservative ECAR-Lite planner.  It covers
    direct table bindings, bounded graph paths and explicit ordinal/rank
    filters.  It abstains from replacement when the query graph is not
    distinguishable, leaving the reader answer intact.
    """

    max_hops = 4
    max_anchors = 12
    max_search_nodes = 12000
    replacement_margin = 1.25
    replacement_threshold = 3.0

    @classmethod
    def _proof_assessment(cls, candidate: dict | None, constraints: dict) -> dict:
        """Classify a proof without treating co-mention as relation evidence.

        Passage ``mentions`` edges generate candidates, but cannot by themselves
        prove the query relation.  A verified proof must contain either an
        executed record-row operation or a non-trivial semantic/table relation
        that overlaps a question relation cue.  The returned gap is suitable
        for a later targeted L2 retrieval request.
        """
        if candidate is None:
            return {"status": "unverified", "verified": False, "proof_gap": ["no_candidate_path"]}
        path = candidate["path"]
        components = candidate["components"]
        nontrivial = [
            edge for edge in path
            if edge.relation not in {"mentions", "linked_passage", "has_record"}
        ]
        relation_terms = _terms(" ".join(edge.relation for edge in nontrivial))
        required = set(constraints["relation_cues"])
        relation_match = bool(required & relation_terms) if required else bool(nontrivial)
        row_execution = candidate["origin"] in {"row_rank", "row_order"}
        ordinal_ok = constraints["ordinal"] is None or components["order"] == 1.0 or row_execution
        coverage_ok = components["constraints"] >= 0.20 or row_execution
        verified = bool(path) and ordinal_ok and coverage_ok and (row_execution or relation_match)
        gaps = []
        if not nontrivial and not row_execution:
            gaps.append("mention_only_path")
        if required and not relation_match and not row_execution:
            gaps.append("missing_relation_witness")
        if not coverage_ok:
            gaps.append("low_constraint_coverage")
        if not ordinal_ok:
            gaps.append("unexecuted_ordinal")
        return {
            "status": "verified" if verified else "partially_grounded",
            "verified": verified,
            "proof_gap": gaps,
            "relation_witness_edge_ids": [edge.identifier for edge in nontrivial],
        }

    @classmethod
    def _edges(cls, trace: dict) -> list[_Edge]:
        edges: list[_Edge] = []
        for index, item in enumerate(trace.get("record_edges", [])):
            edges.append(_Edge(
                f"record:{index}", str(item.get("head", "")), str(item.get("relation", "")),
                str(item.get("tail", "")), str(item.get("source_type") or "table"),
            ))
        for index, item in enumerate(trace.get("edges", [])):
            provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
            edges.append(_Edge(
                f"semantic:{index}", str(item.get("head", "")), str(item.get("relation", "")),
                str(item.get("tail", "")), str(provenance.get("source_type") or "text"),
            ))
        # Make surface labels in passages explicit graph endpoints. Each
        # endpoint remains connected to its originating passage, so recovery
        # can audit the evidence instead of trusting a generated string.
        passages: dict[str, str] = {}
        for node in trace.get("structural_nodes", []):
            if str(node.get("type")) == "Passage":
                context = node.get("context") if isinstance(node.get("context"), dict) else {}
                label = str(node.get("label") or node.get("id") or "")
                content = str(context.get("text") or "")
                if label and content:
                    passages[label] = content
        for item in trace.get("edges", []):
            for context in item.get("contexts") or []:
                if not isinstance(context, dict):
                    continue
                label = str(context.get("source_id") or "")
                content = str(context.get("text") or "")
                if label and content:
                    passages.setdefault(label, content)
        mention_index = 0
        for passage, content in passages.items():
            for mention in sorted(_passage_mentions(content))[:250]:
                edges.append(_Edge(f"mention:{mention_index}", passage, "mentions", mention, "text"))
                mention_index += 1
        return edges

    @classmethod
    def _candidate_values(cls, trace: dict, edges: list[_Edge]) -> dict[str, dict]:
        candidates: dict[str, dict] = {}

        def add(value: object, source: str, *, alias_for: str | None = None) -> None:
            text = str(value or "").strip()
            if _is_internal(text) or len(_normalise(text)) < 2:
                return
            canonical = str(alias_for or text).strip()
            if _is_internal(canonical):
                return
            entry = candidates.setdefault(canonical, {"answer": canonical, "sources": set(), "aliases": set()})
            entry["sources"].add(source)
            entry["aliases"].add(text)

        for node in trace.get("structural_nodes", []):
            if str(node.get("type")) == "Cell":
                add(node.get("value"), "table_cell")
            else:
                add(node.get("label"), "structural_node")
        for node in trace.get("node_metadata", []):
            add(node.get("id"), "kg_node")
        for edge in edges:
            add(edge.head, edge.source_type)
            add(edge.tail, edge.source_type)
        # The resolver trace maps surface aliases to the canonical graph node.
        for alias, canonical in (trace.get("aliases") or {}).items():
            add(canonical, "alias", alias_for=canonical)
            if canonical in candidates:
                candidates[canonical]["aliases"].add(str(alias))
        for entry in candidates.values():
            entry["sources"] = sorted(entry["sources"])
            entry["aliases"] = sorted(entry["aliases"])
        return candidates

    @classmethod
    def _shortest_path(
        cls, adjacency: dict[str, list[tuple[str, _Edge]]], anchors: list[str], answer: str,
    ) -> list[_Edge] | None:
        answer_key = _normalise(answer)
        starts = [anchor for anchor in anchors if _normalise(anchor) != answer_key]
        if not starts:
            return None
        queue = deque((anchor, [], {_normalise(anchor)}) for anchor in starts)
        while queue:
            node, path, seen = queue.popleft()
            if path and _normalise(node) == answer_key:
                return path
            if len(path) >= cls.max_hops:
                continue
            for neighbor, edge in adjacency.get(node, []):
                key = _normalise(neighbor)
                if key in seen:
                    continue
                queue.append((neighbor, [*path, edge], {*seen, key}))
        return None

    @classmethod
    def _bounded_paths(
        cls, adjacency: dict[str, list[tuple[str, _Edge]]], anchors: list[str],
    ) -> dict[str, list[_Edge]]:
        """Run one bounded multi-source BFS for all answer candidates.

        Re-running a BFS per table cell makes post-processing quadratic on a
        large compact graph.  This returns the first (therefore shortest)
        proof found from any lexical question anchor, keyed by normalized node
        label.  The node budget bounds tail latency at serving time.
        """
        queue: deque[tuple[str, list[_Edge]]] = deque()
        seen: set[str] = set()
        paths: dict[str, list[_Edge]] = {}
        for anchor in anchors:
            key = _normalise(anchor)
            if key and key not in seen:
                seen.add(key)
                queue.append((anchor, []))
        while queue and len(seen) < cls.max_search_nodes:
            node, path = queue.popleft()
            node_key = _normalise(node)
            if path:
                paths.setdefault(node_key, path)
            if len(path) >= cls.max_hops:
                continue
            for neighbor, edge in adjacency.get(node, []):
                key = _normalise(neighbor)
                if not key or key in seen:
                    continue
                seen.add(key)
                queue.append((neighbor, [*path, edge]))
        return paths

    @staticmethod
    def _path_nodes(path: list[_Edge]) -> set[str]:
        return {value for edge in path for value in (edge.head, edge.tail)}

    @classmethod
    def _path_components(cls, question: str, answer: str, path: list[_Edge] | None) -> dict[str, float]:
        if not path:
            return {"constraints": 0.0, "path": 0.0, "type": 0.0, "order": 0.0, "text_support": 0.0}
        q_terms = _terms(question)
        rendered_relations = _terms(" ".join(edge.relation for edge in path))
        rendered_nodes = _terms(" ".join(cls._path_nodes(path)))
        relation_overlap = len(q_terms & rendered_relations) / max(len(q_terms), 1)
        node_overlap = len(q_terms & rendered_nodes) / max(len(q_terms), 1)
        number_tokens = set(re.findall(r"\b\d{1,4}\b", question))
        path_text = " ".join(cls._path_nodes(path))
        numeric_coverage = (
            sum(number in path_text for number in number_tokens) / len(number_tokens)
            if number_tokens else 1.0
        )
        ordinal = _ordinal(question)
        order = 0.0
        if ordinal is not None:
            has_rank_relation = any(_RANK_RELATION.search(edge.relation) for edge in path)
            has_ordinal_value = bool(re.search(rf"(?<!\d){ordinal}(?!\d)", path_text))
            order = 1.0 if has_rank_relation and has_ordinal_value else 0.0
        text_support = float(any(edge.source_type == "text" for edge in path))
        return {
            "constraints": round(0.55 * relation_overlap + 0.25 * node_overlap + 0.20 * numeric_coverage, 4),
            "path": round(1.0 / len(path), 4),
            "type": round(_type_score(answer, " ".join(edge.relation for edge in path), _target_type(question)), 4),
            "order": order,
            "text_support": text_support,
        }

    @staticmethod
    def _score(components: dict[str, float]) -> float:
        return round(
            3.5 * components["constraints"] + 1.0 * components["path"]
            + 1.25 * components["type"] + 1.5 * components["order"]
            + 0.5 * components["text_support"], 4,
        )

    @classmethod
    def _row_candidates(cls, question: str, edges: list[_Edge]) -> list[dict]:
        """Generate table denotations for explicit ordinal/rank questions."""
        row_subjects = {edge.tail: edge.head for edge in edges if edge.relation == "has_record"}
        row_values: dict[str, list[_Edge]] = defaultdict(list)
        for edge in edges:
            if edge.head in row_subjects and edge.relation != "has_record" and not _is_internal(edge.tail):
                row_values[edge.head].append(edge)
        ordinal = _ordinal(question)
        question_lower = question.casefold()
        candidates = []
        wants_subject = bool(re.search(r"\b(which|what|name of) (?:the )?(club|team|person|player|winner)\b", question_lower))
        if ordinal is not None:
            for row, values in row_values.items():
                subject = row_subjects[row]
                rank_edges = [
                    edge for edge in values
                    if _RANK_RELATION.search(edge.relation)
                    and re.search(rf"(?<!\d){ordinal}(?!\d)", edge.tail)
                ]
                if not rank_edges:
                    continue
                if wants_subject and not _is_internal(subject):
                    proof = [next(edge for edge in edges if edge.tail == row and edge.relation == "has_record"), rank_edges[0]]
                    components = cls._path_components(question, subject, proof)
                    components["order"] = 1.0
                    candidates.append({"answer": subject, "path": proof, "components": components, "origin": "row_rank"})
        # ``first formed`` / ``last elected`` denote an ordering over a table
        # column rather than a row whose Rank cell literally contains 1.
        temporal_terms = [
            term for term in _TEMPORAL_TERMS
            if re.search(rf"\b{re.escape(term)}\b", question_lower)
        ]
        wants_extreme = bool(re.search(r"\b(first|earliest|oldest|last|latest|newest|most recent)\b", question_lower))
        if wants_subject and temporal_terms and wants_extreme:
            sortable = []
            for row, values in row_values.items():
                for edge in values:
                    if not any(term in edge.relation.casefold() for term in temporal_terms):
                        continue
                    match = re.search(r"(?:1[5-9]|20)\d{2}|\d+(?:\.\d+)?", edge.tail)
                    if match:
                        sortable.append((float(match.group()), row, edge))
            if sortable:
                reverse = bool(re.search(r"\b(last|latest|newest|most recent)\b", question_lower))
                _, row, order_edge = sorted(sortable, reverse=reverse, key=lambda item: item[0])[0]
                subject = row_subjects[row]
                record_edge = next(edge for edge in edges if edge.tail == row and edge.relation == "has_record")
                proof = [record_edge, order_edge]
                components = cls._path_components(question, subject, proof)
                components["order"] = 1.0
                candidates.append({"answer": subject, "path": proof, "components": components, "origin": "row_order"})
        return candidates

    @classmethod
    def recover(cls, *, question: str, llm_answer: str, kg_trace: dict) -> dict:
        """Return a conservative ECAR decision and auditable candidate ranking."""
        constraints = _query_constraints(question)
        edges = cls._edges(kg_trace)
        candidates = cls._candidate_values(kg_trace, edges)
        adjacency: dict[str, list[tuple[str, _Edge]]] = defaultdict(list)
        for edge in edges:
            adjacency[edge.head].append((edge.tail, edge))
            adjacency[edge.tail].append((edge.head, edge))
        q_terms = _terms(question)
        anchors = sorted(
            (answer for answer in candidates if _terms(answer) & q_terms),
            key=lambda answer: (-len(_terms(answer) & q_terms), len(answer), answer),
        )[:cls.max_anchors]
        paths = cls._bounded_paths(adjacency, anchors)

        scored: list[dict] = []
        for answer, metadata in candidates.items():
            path = paths.get(_normalise(answer))
            components = cls._path_components(question, answer, path)
            score = cls._score(components)
            if path:
                scored.append({
                    "answer": answer, "path": path, "components": components,
                    "score": score, "origin": "graph_path", "sources": metadata["sources"],
                })
        scored.extend(cls._row_candidates(question, edges))
        for candidate in scored:
            candidate["score"] = candidate.get("score", cls._score(candidate["components"]))
            candidate["path"] = candidate["path"][:cls.max_hops]
        # Keep one proof per denotation, deterministically.
        best_by_answer: dict[str, dict] = {}
        for candidate in scored:
            current = best_by_answer.get(candidate["answer"])
            if current is None or candidate["score"] > current["score"]:
                best_by_answer[candidate["answer"]] = candidate
        ranked = sorted(best_by_answer.values(), key=lambda item: (-item["score"], len(item["path"]), item["answer"]))

        answer_norm = _normalise(llm_answer)
        answer_tokens = answer_norm.split()
        raw_llm_supported = any(_normalise(candidate) == answer_norm for candidate in candidates)

        def is_contiguous_label(candidate: str) -> bool:
            candidate_tokens = _normalise(candidate).split()
            return bool(candidate_tokens) and any(
                answer_tokens[index:index + len(candidate_tokens)] == candidate_tokens
                for index in range(len(answer_tokens) - len(candidate_tokens) + 1)
            )

        def is_safe_canonical_label(candidate: str) -> bool:
            candidate_tokens = _normalise(candidate).split()
            content_terms = _terms(candidate)
            if "," in llm_answer and answer_tokens[:len(candidate_tokens)] != candidate_tokens:
                return False
            if re.fullmatch(r"[+-]?\d[\d,.%]*", candidate.strip()):
                return _target_type(question) == "numeric"
            if len(content_terms) >= 2 and all(len(term) > 1 for term in content_terms):
                return True
            # A one-word extraction is safe only when the reader supplied an
            # explicit comma-separated list beginning with that label. This
            # permits "Buttercup, Primrose" -> "Buttercup", while rejecting
            # lossy fragments such as "Robert E" or "Gaillard".
            return (
                len(content_terms) == 1
                and len(candidate_tokens) == 1
                and answer_tokens[:1] == candidate_tokens
                and "," in llm_answer
            )

        mapped = [
            item for item in ranked
            if answer_norm and (
                _normalise(item["answer"]) == answer_norm
                or (
                    # Canonicalization may only delete a decoration from the
                    # reader answer (role prefix, parenthetical year, etc.).
                    # Bag-of-words matching let a passage phrase append a
                    # stop word (for example "Santa Clara for"), which is
                    # neither a canonical label nor a safe recovery.
                    is_safe_canonical_label(item["answer"])
                    and is_contiguous_label(item["answer"])
                )
            )
        ]
        exact_mapped = [item for item in mapped if _normalise(item["answer"]) == answer_norm]
        # Preserve an answer that already is a dataset label. Otherwise use
        # the longest contained label, not the highest generic graph score.
        numeric_mapped = [
            item for item in mapped
            if re.fullmatch(r"[+-]?\d[\d,.%]*", str(item["answer"]).strip())
        ]
        selected = (
            exact_mapped[0]
            if exact_mapped
            else max(numeric_mapped, key=lambda item: item["score"])
            if _target_type(question) == "numeric" and numeric_mapped
            else max(mapped, key=lambda item: (len(_normalise(item["answer"])), item["score"]))
            if mapped else None
        )
        decision = "llm_retained"
        recovered_answer = str(llm_answer or "")
        top = ranked[0] if ranked else None
        next_score = ranked[1]["score"] if len(ranked) > 1 else float("-inf")
        if top:
            # A deterministic replacement requires every explicit ordinal
            # constraint to be satisfied and a margin over the runner-up.
            order_required = _ordinal(question) is not None
            enough_constraints = top["components"]["constraints"] >= 0.35
            satisfies_order = not order_required or top["components"]["order"] == 1.0
            if top["score"] >= cls.replacement_threshold and enough_constraints and satisfies_order and top["score"] - next_score >= cls.replacement_margin:
                recovered_answer = top["answer"]
                selected = top
                decision = "deterministic_recovery"
        # Canonicalization is safe only with an actual graph proof.  No lexical
        # answer similarity enters the evidence score.
        if (
            decision != "deterministic_recovery"
            and not raw_llm_supported
            and selected
            and selected["score"] >= 1.5
        ):
            recovered_answer = selected["answer"]
            decision = "llm_canonicalized"

        proof = cls._proof_assessment(selected, constraints)

        def audit(candidate: dict) -> dict:
            return {
                "answer": candidate["answer"], "score": candidate["score"],
                "origin": candidate["origin"], "components": candidate["components"],
                "edge_ids": [edge.identifier for edge in candidate["path"]],
                "steps": [f"{edge.head} --{edge.relation}--> {edge.tail}" for edge in candidate["path"]],
            }

        return {
            "enabled": True,
            "llm_answer": str(llm_answer or ""),
            "answer": recovered_answer,
            "decision": decision,
            "candidate_count": len(candidates),
            "connected_candidate_count": len(ranked),
            "anchors": anchors,
            "query_constraints": constraints,
            "selected": audit(selected) if selected else None,
            "top_candidates": [audit(candidate) for candidate in ranked[:5]],
            "proof_status": proof["status"],
            "proof_gap": proof["proof_gap"],
            "relation_witness_edge_ids": proof.get("relation_witness_edge_ids", []),
            "evidence_verified": proof["verified"],
        }
