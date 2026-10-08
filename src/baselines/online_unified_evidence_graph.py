"""Online Unified Evidence Graph: full subgraph plus non-filtering path views."""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from copy import deepcopy

from src.baselines.kg_payload import deduplicate_edge_contexts
from src.baselines.oueg_prompt_compression import (
    CompactOUEGPromptBuilder,
    OUEGPromptCompressionConfig,
)
from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
from src.llm.client import get_provider, llm_call
from src.planning.grounded_paths import GroundedPathPlanner
from src.retrieval.coarse_retrieval import two_stage_retrieve


_STOP_TERMS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "that",
    "this", "to", "was", "what", "when", "where", "which", "who", "whose", "with",
}

_ORDINAL_WORD_VALUES = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
_ORDINAL_PATTERN = re.compile(
    r"\b(?:(?P<word>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    r"|(?P<number>\d+)(?:st|nd|rd|th))\b",
    re.IGNORECASE,
)


def _ordinal_rank(question: str) -> int | None:
    """Extract an explicit ordinal rank, when the question supplies one."""
    match = _ORDINAL_PATTERN.search(question)
    if match is None:
        return None
    if word := match.group("word"):
        return _ORDINAL_WORD_VALUES[word.casefold()]
    return int(match.group("number"))


class _VerbatimOUEGPromptBuilder:
    """A deliberately uncompressed control serializer for the OUEG ablation."""


    @staticmethod
    def build(*, question: str, records: list[dict], contexts_by_source_id: dict[str, dict], suggested_paths: list[dict], ordering_hint: dict, ambiguity: dict, path_generation: dict) -> dict:
        payload = {
            "format": "oueg-verbatim-v1",
            "question": question,
            "records": records,
            "contexts_by_source_id": contexts_by_source_id,
            "suggested_paths": suggested_paths,
            "ordering_hint": ordering_hint,
            "ambiguity": ambiguity,
            "path_generation": path_generation,
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        return {
            "payload": payload,
            "json": rendered,
            "stats": {
                "compression_enabled": False,
                "full_edge_count": len(records),
                "context_count": len(contexts_by_source_id),
                "prompt_payload_chars": len(rendered),
                "all_edges_represented": True,
            },
        }


    @staticmethod
    def prompt(*, question: str, compact_json: str, tie_break_hint: str = "") -> str:
        return f"""Answer the question using the complete uncompressed OUEG payload.\n\nEvery record and source context is shown verbatim; suggested paths are reading guides only. Return only the shortest answer span.{tie_break_hint}\n\nQuestion: {question}\nUncompressed OUEG payload: {compact_json}\nAnswer:"""


class OnlineUnifiedEvidenceGraphBaseline:
    """Answer from the whole retrieved KG; paths are candidate reading guides only."""

    method_name = "online_unified_evidence_graph"

    def __init__(self, config: RAGConfig | None = None, *, kg_builder=None, prompt_builder=None):
        self.config = config or RAGConfig()
        self.config.validate()
        self.prompt_builder = prompt_builder or (
            CompactOUEGPromptBuilder(OUEGPromptCompressionConfig(
                context_mode=self.config.oueg_context_mode,
                include_lexical_tiebreak=self.config.use_lexical_tiebreak,
            )) if self.config.use_prompt_compression else _VerbatimOUEGPromptBuilder()
        )
        self.kg_builder = kg_builder or OnlineKGBuilder(EntityRelationExtractor(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            use_llm_text_enrichment=False,
            use_rule_text_triples=self.config.use_rule_text_triples,
        ))

    @staticmethod
    def _terms(value: str) -> set[str]:
        return {
            term for term in re.findall(r"[a-z0-9]+", str(value).casefold())
            if term not in _STOP_TERMS
        }

    @staticmethod
    def _edge_label(edge: dict) -> str:
        return f'{edge.get("head", "")} --{edge.get("relation", "")}--> {edge.get("tail", "")}'

    @classmethod
    def _edge_overlap(cls, edge: dict, question_terms: set[str]) -> float:
        rendered = " ".join(str(edge.get(key, "")) for key in (
            "head", "relation", "tail", "column_name",
        ))
        rendered += " " + " ".join(
            str(context.get(key, ""))
            for context in edge.get("contexts", [])
            for key in ("context_before", "text")
        )
        return len(cls._terms(rendered) & question_terms) / max(len(question_terms), 1)

    @staticmethod
    def _append_sort_key(values: dict, column: str, value: str) -> None:
        if column not in values:
            values[column] = value
        elif values[column] != value:
            existing = values[column]
            values[column] = [existing, value] if not isinstance(existing, list) else [*existing, value]

    @staticmethod
    def _lexical_overlap_with_bridge(entity: object, bridge: object) -> float:
        """Fraction of bridge-name tokens present in the candidate entity name."""
        bridge_terms = OnlineUnifiedEvidenceGraphBaseline._terms(str(bridge))
        if not bridge_terms:
            return 0.0
        return round(
            len(OnlineUnifiedEvidenceGraphBaseline._terms(str(entity)) & bridge_terms)
            / len(bridge_terms),
            4,
        )

    @staticmethod
    def _target_entity_type(question: str) -> str:
        lowered = question.casefold()
        if re.search(r"\b(how many|how much|number of|population|inhabitants?|count)\b", lowered):
            return "numeric"
        if re.search(r"\b(name of (the )?(club|team)|which (club|team)|what (club|team))\b", lowered):
            return "club"
        if re.search(r"\b(when|what year|which year|date)\b", lowered):
            return "temporal"
        if re.search(r"\b(where|which city|what city|which town|what town)\b", lowered):
            return "location"
        return "entity"

    @classmethod
    def _matches_target_type(cls, node: str, edge: dict, target_type: str) -> bool:
        value = str(node)
        relation = str(edge.get("relation", "")).casefold()
        if target_type == "numeric":
            return bool(re.fullmatch(r"[+-]?\d[\d,.%]*", value.strip())) or bool(
                re.search(r"population|count|number|total|rank|position|year", relation)
            )
        if target_type == "club":
            return bool(re.search(r"\b(club|fc|f\.?c\.?|team|united)\b", value, re.I))
        if target_type == "temporal":
            return bool(re.search(r"\b(?:1[5-9]|20)\d{2}\b", value)) or bool(
                re.search(r"date|year|formed|founded|opened|elected|established", relation)
            )
        if target_type == "location":
            return bool(re.search(r"city|town|suburb|location|located|based", relation, re.I))
        return bool(value and not value.startswith(("table:", "passage:")))

    @classmethod
    def _path_metadata(
        cls,
        question: str,
        records: list[dict],
        edges: list[dict],
        *,
        anchor_entity: object,
        bridge_entity: object,
    ) -> dict:
        score, components = GroundedPathPlanner().score_edges(question, records, edges)
        lexical_bridge = cls._lexical_overlap_with_bridge(anchor_entity, bridge_entity)
        return {
            "score": score,
            "score_components": components,
            "lexical_overlap_with_bridge_entity": lexical_bridge,
            # The legacy question-overlap value remains useful for auditing,
            # while the bridge-specific value is the tie-break signal.
            "lexical_overlap_score": round(max((cls._edge_overlap(edge, cls._terms(question)) for edge in edges), default=0.0), 4),
            "presentation_score": round(score + lexical_bridge, 4),
        }

    @classmethod
    def _candidate_rows(cls, question: str, records: list[dict]) -> list[dict]:
        """Return every table row as a candidate, with no rank or top-k cutoff."""
        question_terms = cls._terms(question)
        by_head: dict[str, list[dict]] = defaultdict(list)
        for edge in records:
            by_head[str(edge.get("head", ""))].append(edge)

        linked_by_entity: dict[str, dict] = {}
        for edge in records:
            if edge.get("relation") == "linked_passage" and edge.get("contexts"):
                linked_by_entity.setdefault(str(edge.get("head")), edge)
        semantic_by_head: dict[str, list[dict]] = defaultdict(list)
        for edge in records:
            if (
                edge.get("structural") is False
                and edge.get("relation") != "linked_passage"
                and cls._edge_overlap(edge, question_terms) > 0
            ):
                semantic_by_head[str(edge.get("head"))].append(edge)

        candidates = []
        row_entries = [
            edge for edge in records
            if edge.get("structural") and edge.get("relation") == "has_record"
            and str(edge.get("tail", "")).startswith("table:")
            and ":row:" in str(edge.get("tail", ""))
        ]
        seen_rows = set()
        for anchor in sorted(row_entries, key=lambda edge: (
            str(edge.get("source_id", "")),
            int(edge.get("row_index", -1)) if edge.get("row_index") is not None else -1,
            str(edge.get("tail", "")),
            str(edge.get("head", "")),
        )):
            row_id = str(anchor["tail"])
            if row_id in seen_rows:
                continue
            seen_rows.add(row_id)
            row_edges = [
                edge for edge in by_head[row_id]
                if edge.get("structural")
                and edge.get("relation") != "has_record"
                and not edge.get("cell_node")
                and ":cell:" not in str(edge.get("tail", ""))
            ]
            sort_keys: dict[str, object] = {}
            for edge in row_edges:
                column = str(edge.get("column_name") or edge.get("relation") or "value")
                cls._append_sort_key(sort_keys, column, str(edge.get("tail", "")))

            # The chain is only a reading view. Every row remains in the output,
            # even where its most useful bridge has a low score.
            ranked_row_edges = sorted(
                row_edges,
                key=lambda edge: (
                    -(cls._edge_overlap(edge, question_terms)
                      + cls._edge_overlap(linked_by_entity.get(str(edge.get("tail")), {}), question_terms)),
                    str(edge.get("column_name", "")), str(edge.get("tail", "")),
                ),
            )
            guide_edges = [anchor]
            bridge_entity = ""
            if ranked_row_edges:
                bridge = ranked_row_edges[0]
                guide_edges.append(bridge)
                bridge_entity = str(bridge.get("tail", ""))
                linked = linked_by_entity.get(bridge_entity)
                if linked is not None:
                    guide_edges.append(linked)
                guide_edges.extend(sorted(
                    semantic_by_head.get(bridge_entity, []),
                    key=lambda edge: (-cls._edge_overlap(edge, question_terms), str(edge.get("relation", "")), str(edge.get("tail", ""))),
                ))
            row_index = anchor.get("row_index")
            candidates.append({
                "path_id": "row_" + str(row_index) if row_index is not None else row_id,
                "path_kind": "row_bundle",
                "role": "candidate",
                "row_order_index": row_index,
                "row_id": row_id,
                "anchor_entity": anchor.get("head"),
                "bridge_entity": bridge_entity,
                "target_entity_type": cls._target_entity_type(question),
                "edge_ids": [edge.get("edge_id") for edge in guide_edges],
                "steps": [cls._edge_label(edge) for edge in guide_edges],
                "sort_keys": sort_keys,
                **cls._path_metadata(
                    question, records, guide_edges,
                    anchor_entity=anchor.get("head"), bridge_entity=bridge_entity,
                ),
            })
        return candidates

    @classmethod
    def _seed_expansion_paths(
        cls, question: str, records: list[dict], *, max_enumerated: int = 50,
    ) -> list[dict]:
        """Enumerate target-aware DFS reading paths without score-based selection.

        The only cap is a documented safety bound on *enumeration*, after target
        typing reduces branches. Structural and text/relation-extraction records
        share the same adjacency, and passage nodes are traversable intermediates.
        """
        target_type = cls._target_entity_type(question)
        question_terms = cls._terms(question)
        adjacency: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for edge in records:
            head, tail = str(edge.get("head", "")), str(edge.get("tail", ""))
            adjacency[head].append((tail, edge))
            adjacency[tail].append((head, edge))
        for node in adjacency:
            adjacency[node].sort(key=lambda item: (
                -int(cls._matches_target_type(item[0], item[1], target_type)),
                -len((cls._terms(item[0]) | cls._terms(item[1].get("relation", ""))) & question_terms),
                str(item[1].get("edge_id", "")),
            ))

        seeds = [
            node for node in sorted(adjacency)
            if not node.startswith(("table:", "passage:"))
            and cls._terms(node) & question_terms
        ]
        # Question wording can name only a relation. In that case seed every
        # matching relation endpoint, still without a score cutoff.
        if not seeds:
            seeds = sorted({
                str(value) for edge in records
                if cls._terms(str(edge.get("relation", ""))) & question_terms
                for value in (edge.get("head"), edge.get("tail"))
                if value is not None and not str(value).startswith("table:")
            })

        paths, signatures = [], set()
        for seed in seeds:
            stack = [(seed, [seed], [], set())]
            while stack and len(paths) < max_enumerated:
                current, nodes, edges, used_ids = stack.pop()
                # A linked passage is an intermediate. Completion requires the
                # requested type; text triples after it remain expandable.
                # Row-Bundle already represents every table-only candidate.
                # DFS adds value when it continues into extracted text facts;
                # requiring one semantic text edge prevents combinatorial table
                # detours while preserving the full KG as the safety net.
                reaches_text_fact = any(
                    edge.get("structural") is False
                    and edge.get("relation") != "linked_passage"
                    for edge in edges
                )
                if edges and reaches_text_fact and cls._matches_target_type(current, edges[-1], target_type):
                    signature = tuple((str(edge.get("edge_id")), edge.get("direction", "forward")) for edge in edges)
                    if signature not in signatures:
                        signatures.add(signature)
                        paths.append({
                            "path_id": f"seed_{len(paths)}",
                            "path_kind": "seed_expansion",
                            "role": "candidate",
                            "row_order_index": None,
                            "row_id": None,
                            "anchor_entity": seed,
                            "bridge_entity": current,
                            "target_entity_type": target_type,
                            "edge_ids": [edge.get("edge_id") for edge in edges],
                            "steps": [cls._edge_label(edge) for edge in edges],
                            "sort_keys": {},
                            **cls._path_metadata(question, records, edges, anchor_entity=seed, bridge_entity=current),
                        })
                if len(edges) >= 5:
                    continue
                for neighbor, raw_edge in reversed(adjacency.get(current, [])):
                    edge_id = str(raw_edge.get("edge_id"))
                    if edge_id in used_ids or neighbor in nodes:
                        continue
                    direction = "forward" if current == str(raw_edge.get("head")) else "reverse"
                    traversed = {**raw_edge, "traversal_from": current, "traversal_to": neighbor, "direction": direction}
                    stack.append((neighbor, [*nodes, neighbor], [*edges, traversed], {*used_ids, edge_id}))
            if len(paths) >= max_enumerated:
                break
        return paths

    @staticmethod
    def _sort_value(value: object) -> tuple[int, object]:
        if isinstance(value, list):
            value = value[0] if value else ""
        text = str(value or "")
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
        if match:
            return (0, float(match.group()))
        return (1, text.casefold())

    @classmethod
    def _ordering_hint(cls, question: str, candidates: list[dict]) -> tuple[dict, list[dict]]:
        lowered = question.casefold()
        ordinal_rank = _ordinal_rank(lowered)
        columns = sorted({
            str(column)
            for candidate in candidates
            for column in candidate.get("sort_keys", {})
        })
        reading_priority = sorted(
            candidates,
            key=lambda candidate: (
                -float(candidate.get("presentation_score", candidate.get("score", 0.0))),
                candidate.get("row_order_index") if candidate.get("row_order_index") is not None else float("inf"),
                str(candidate.get("path_id", "")),
            ),
        )
        # An ordinal changes the answer target (e.g. "how many goals did the
        # tenth player score?"); it must take precedence over a generic count.
        if ordinal_rank is None and re.search(r"\b(how many|number of|count)\b", lowered):
            return ({
                "detected_signal": "counting",
                "sort_by_column": None,
                "direction": None,
                "note": "Counting signal detected; retain every structural candidate and count only after applying question constraints. Within no explicit table order, paths use score metadata only as reading priority.",
            }, reading_priority)

        temporal = bool(re.search(
            r"\b(earliest|oldest|elected|before|after|previous|next|last|latest|"
            r"most\s+recent|recently|newest)\b",
            lowered,
        ))
        if ordinal_rank is None and not temporal:
            return ({
                "detected_signal": "none",
                "sort_by_column": None,
                "direction": None,
                "note": "No ordering signal detected; all candidates are retained and displayed by reading priority only.",
            }, reading_priority)

        question_terms = cls._terms(question)
        def column_score(column: str) -> tuple[int, str]:
            terms = cls._terms(column)
            score = 10 * len(terms & question_terms)
            if terms & {"date", "year", "opened", "founded", "formed", "elected", "established"}:
                score += 4
            if terms & {"position", "rank", "order", "number"}:
                score += 3
            return (score, column)

        ordinal_columns = [
            column for column in columns
            if cls._terms(column) & {"position", "rank", "order", "number"}
        ]
        # For ordinal questions, prefer an explicit rank/order column rather
        # than an incidental temporal or numeric column.
        sort_by = max(
            ordinal_columns if ordinal_rank is not None and ordinal_columns else columns,
            key=column_score,
        ) if columns else None
        if not sort_by:
            return ({
                "detected_signal": "ordinal_rank" if ordinal_rank is not None else "sequence_prev_next",
                "sort_by_column": None,
                "direction": None,
                "ordinal_rank": ordinal_rank,
                "note": "Ordering signal detected but no sortable table column was found; keep original table-row order.",
            }, candidates)
        # With "before X", the immediately preceding entity should be shown
        # first.  The same reverse ordering applies to recent/newest wording.
        direction = "descending" if re.search(
            r"\b(last|latest|after|before|most\s+recent|recently|newest)\b",
            lowered,
        ) else "ascending"
        # Stable sort preserves score-based reading priority only among paths
        # with the same table ordering value; it never drops a candidate.
        ordered = sorted(
            reading_priority,
            key=lambda candidate: cls._sort_value(candidate.get("sort_keys", {}).get(sort_by)),
            reverse=direction == "descending",
        )
        signal = (
            "ordinal_rank" if ordinal_rank is not None
            else "temporal_first" if re.search(r"\b(earliest|oldest|elected)\b", lowered)
            else "sequence_prev_next"
        )
        return ({
            "detected_signal": signal,
            "sort_by_column": sort_by,
            "direction": direction,
            "ordinal_rank": ordinal_rank,
            "note": f"Candidates are sorted by the displayed `{sort_by}` values in {direction} order; they remain a complete candidate set, not a shortlist.",
        }, ordered)

    @classmethod
    def _ambiguity_assessment(cls, question: str, row_candidates: list[dict]) -> dict:
        """Describe structural multi-answer cases without discarding evidence."""
        grouped: dict[str, list[dict]] = defaultdict(list)
        bridge_labels: dict[str, str] = {}
        for candidate in row_candidates:
            bridge = str(candidate.get("bridge_entity", "")).strip()
            anchor = str(candidate.get("anchor_entity", "")).strip()
            if not bridge or not anchor:
                continue
            key = " ".join(cls._terms(bridge))
            if key:
                grouped[key].append(candidate)
                bridge_labels.setdefault(key, bridge)

        groups = []
        for key, members in grouped.items():
            unique = {
                (str(member.get("path_id")), str(member.get("anchor_entity"))): member
                for member in members
            }
            members = list(unique.values())
            if len({str(member.get("anchor_entity")) for member in members}) < 2:
                continue
            highest_score = max(float(member.get("score", 0.0)) for member in members)
            top_scored = [
                member for member in members
                if abs(float(member.get("score", 0.0)) - highest_score) <= 1e-4
            ]
            score_collision = len(top_scored) > 1
            lexical_winner = None
            if score_collision:
                highest_lexical = max(
                    float(member.get("lexical_overlap_with_bridge_entity", 0.0))
                    for member in top_scored
                )
                lexical_top = [
                    member for member in top_scored
                    if abs(float(member.get("lexical_overlap_with_bridge_entity", 0.0)) - highest_lexical) <= 1e-4
                ]
                if len(lexical_top) == 1 and highest_lexical > 0.0:
                    lexical_winner = lexical_top[0]
            groups.append({
                "bridge_entity": bridge_labels[key],
                "candidate_count": len(members),
                "status": "SCORE_COLLISION_TIE" if score_collision else "MULTIPLE_STRUCTURAL_CANDIDATES",
                "score_collision_tie": score_collision,
                "candidates": [
                    {
                        "path_id": member["path_id"],
                        "entity": member.get("anchor_entity"),
                        "row_id": member.get("row_id"),
                        "row_order_index": member.get("row_order_index"),
                        "score": member.get("score"),
                        "lexical_overlap_with_bridge_entity": member.get("lexical_overlap_with_bridge_entity"),
                    }
                    for member in sorted(members, key=lambda member: (
                        -float(member.get("presentation_score", member.get("score", 0.0))),
                        str(member.get("path_id")),
                    ))
                ],
                "lexical_tiebreak": {
                    "strategy": "lexical_overlap_with_bridge_entity",
                    "eligible": score_collision,
                    "winner": lexical_winner.get("anchor_entity") if lexical_winner else None,
                    "winner_path_id": lexical_winner.get("path_id") if lexical_winner else None,
                    "note": "A unique lexical winner is only a weak tie-break signal; it is not additional factual evidence.",
                },
            })

        groups.sort(key=lambda group: (
            -group["candidate_count"],
            -int(group["score_collision_tie"]),
            str(group["bridge_entity"]).casefold(),
        ))
        collision_groups = [group for group in groups if group["score_collision_tie"]]
        unique_lexical_winners = [
            group for group in collision_groups
            if group["lexical_tiebreak"]["winner"] is not None
        ]
        selected_winner = (
            unique_lexical_winners[0]["lexical_tiebreak"]
            if len(groups) == 1 and len(unique_lexical_winners) == 1
            else None
        )
        return {
            "is_ambiguous": bool(groups),
            "status": "SCORE_COLLISION_TIE" if collision_groups else (
                "MULTIPLE_STRUCTURAL_CANDIDATES" if groups else "UNAMBIGUOUS"
            ),
            "groups": groups,
            "selective_prediction": {
                "available_policies": ["prompt", "return_candidates", "lexical_tiebreak"],
                "lexical_tiebreak_winner": selected_winner["winner"] if selected_winner else None,
                "lexical_tiebreak_path_id": selected_winner["winner_path_id"] if selected_winner else None,
                "lexical_tiebreak_is_safe": selected_winner is not None,
            },
        }

    @staticmethod
    def _ambiguous_answer(ambiguity: dict) -> str:
        candidates = [
            str(candidate["entity"])
            for group in ambiguity.get("groups", [])
            for candidate in group.get("candidates", [])
        ]
        candidates = list(dict.fromkeys(candidates))
        return (
            f"Ambiguous: {len(candidates)} candidates satisfy the structural condition: "
            + "; ".join(candidates)
            + ". Please clarify the intended entity."
        )

    @staticmethod
    def _complete_subgraph_records(kg_trace: dict, path_records: list[dict]) -> list[dict]:
        """Add trace-only Table/Row/Cell/Column edges to the reasoning view.

        ``path_edge_records`` has semantic facts and row records. The trace also
        contains topology-only edges such as Table→Row and Cell→Column. OUEG
        includes their union so the subgraph really contains every KG edge.
        """
        # ``edge_id`` values from individual table/text sources are local and
        # can repeat. OUEG path references must be unambiguous across their
        # union, so retain the source id for audit and assign a union-local id.
        records = []
        for index, edge in enumerate(path_records):
            copied = dict(edge)
            copied["source_edge_id"] = copied.get("edge_id")
            copied["edge_id"] = f"kg:{index}"
            records.append(copied)
        seen = {
            (str(edge.get("head")), str(edge.get("relation")), str(edge.get("tail")))
            for edge in records
        }
        for index, edge in enumerate(kg_trace.get("structural_edges", [])):
            identity = (str(edge.get("head")), str(edge.get("relation")), str(edge.get("tail")))
            if identity in seen:
                continue
            records.append({
                "edge_id": f"structural:{index}",
                "head": edge.get("head"),
                "relation": edge.get("relation"),
                "tail": edge.get("tail"),
                "source_type": "table",
                "source_id": None,
                "row_index": None,
                "column_name": None,
                "header_path": None,
                "structural": True,
                "contexts": [],
            })
            seen.add(identity)
        return records

    @staticmethod
    def _without_record_nodes(records: list[dict]) -> list[dict]:
        """Flatten row hubs into direct subject--value edges for one control."""
        row_subjects = {str(edge.get("tail")): str(edge.get("head")) for edge in records if edge.get("relation") == "has_record"}
        flattened = []
        for edge in records:
            copied = dict(edge)
            head, tail = str(copied.get("head", "")), str(copied.get("tail", ""))
            if copied.get("structural"):
                if copied.get("relation") == "has_record" or copied.get("cell_node"):
                    continue
                if head in row_subjects:
                    if ":cell:" in tail:
                        continue
                    copied["head"] = row_subjects[head]
                elif any(marker in value for value in (head, tail) for marker in (":row:", ":cell:", ":column:")):
                    continue
            flattened.append(copied)
        return flattened


    @staticmethod
    def _annotated_subgraph_nodes(
        kg_trace: dict, records: list[dict], suggested_paths: list[dict], *,
        include_trace_topology: bool = True,
    ) -> list[dict]:
        """Return every semantic/structural node with non-filtering path metadata."""
        nodes: dict[str, dict] = {}
        for node in kg_trace.get("node_metadata", []):
            node_id = str(node.get("id"))
            nodes[node_id] = {
                "id": node_id,
                "types": sorted(set(node.get("types", []))),
                "contexts": [dict(context) for context in node.get("contexts", [])],
            }
        for node in kg_trace.get("structural_nodes", []) if include_trace_topology else []:
            node_id = str(node.get("id"))
            current = nodes.setdefault(node_id, {"id": node_id, "types": [], "contexts": []})
            node_type = node.get("type")
            if node_type and node_type not in current["types"]:
                current["types"].append(node_type)
            for key in ("label", "value", "row_index", "column", "context"):
                if key in node:
                    current[key] = node[key]
        for edge in records:
            for value in (edge.get("head"), edge.get("tail")):
                if value is not None:
                    nodes.setdefault(str(value), {"id": str(value), "types": [], "contexts": []})

        edges_by_id = {str(edge.get("edge_id")): edge for edge in records}
        for path in suggested_paths:
            for step_index, edge_id in enumerate(path.get("edge_ids", []), start=1):
                edge = edges_by_id.get(str(edge_id))
                if edge is None:
                    continue
                annotation = {
                    "path_id": path["path_id"],
                    "step_index": step_index,
                    "role": "candidate",
                    "row_order_index": path.get("row_order_index"),
                }
                for value in (edge.get("head"), edge.get("tail")):
                    if value is None:
                        continue
                    memberships = nodes[str(value)].setdefault("path_annotations", [])
                    if annotation not in memberships:
                        memberships.append(dict(annotation))
        for node in nodes.values():
            node["types"] = sorted(node["types"])
            node.setdefault("path_annotations", [])
        return sorted(nodes.values(), key=lambda node: node["id"])

    @staticmethod
    def _request_token_limit(provider, configured: int) -> int:
        model = str(getattr(provider, "model", "")).casefold()
        needs_reasoning_budget = bool(getattr(provider, "reasoning_enabled", False))
        return max(configured, 512) if needs_reasoning_budget or "gpt-oss" in model else configured

    @staticmethod
    def _short_answer(value: object) -> str:
        """Normalise an answer field without turning abstention into an answer."""
        lines = str(value or "").strip().splitlines()
        answer = lines[0].strip() if lines else ""
        return "" if answer.casefold().strip(" .") in {"", "none", "unknown", "n/a", "na", "null"} else answer

    @classmethod
    def _parse_adaptive_response(cls, raw: str) -> tuple[str, dict]:
        """Parse an answer or a soft focus handoff from the first reader call.

        The parser deliberately accepts a plain non-empty span for backwards
        compatibility with models that ignore the protocol.  A malformed or
        empty response is not silently promoted to a guessed answer.
        """
        text = str(raw or "").strip()
        answer_match = re.search(r"FINAL[ _]+ANSWER\s*:\s*(.+)", text, re.I)
        answer = cls._short_answer(answer_match.group(1) if answer_match else "")
        if answer_match:
            return answer, {}
        needs_focus = bool(re.search(r"NEED_FOCUS\s*:", text, re.I))
        if not needs_focus:
            plain = cls._short_answer(text)
            return plain, {}

        hint = {"raw": text, "candidates": [], "bottleneck": ""}
        json_match = re.search(r"NEED_FOCUS\s*:\s*(\{.*\})", text, re.I | re.S)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                values = parsed.get("candidates", [])
                hint["candidates"] = values if isinstance(values, list) else [values]
                hint["bottleneck"] = str(parsed.get("bottleneck") or parsed.get("reason") or "")
        if not hint["candidates"]:
            candidates_match = re.search(r"Candidates\s*:\s*\[([^\]]*)\]", text, re.I | re.S)
            if candidates_match:
                hint["candidates"] = [
                    item.strip().strip("'\"")
                    for item in candidates_match.group(1).split(",") if item.strip()
                ]
        if not hint["bottleneck"]:
            reason_match = re.search(r"(?:Reason|Bottleneck)\s*:\s*(.+)", text, re.I)
            hint["bottleneck"] = reason_match.group(1).strip() if reason_match else ""
        return "", hint

    @staticmethod
    def _focus_candidate_rows(ambiguity: dict, row_candidates: list[dict]) -> list[dict]:
        """Return a small *pointer* set; no candidate is removed from evidence."""
        collision_members = [
            candidate
            for group in ambiguity.get("groups", [])
            if group.get("status") == "SCORE_COLLISION_TIE"
            for candidate in group.get("candidates", [])
        ]
        if collision_members:
            return collision_members[:3]
        return [
            {
                "entity": candidate.get("anchor_entity"),
                "row_id": candidate.get("row_id"),
                "bridge_entity": candidate.get("bridge_entity"),
                "path_id": candidate.get("path_id"),
            }
            for candidate in row_candidates[:3]
        ]

    @classmethod
    def _focus_handoff(cls, model_hint: dict, ambiguity: dict, row_candidates: list[dict]) -> dict:
        """Validate model hints against graph candidates, then add a local fallback.

        Hints never determine which evidence is serialized in the verification
        prompt.  They only make a few already-present candidate records easier
        for the reader to locate.
        """
        pointer_rows = cls._focus_candidate_rows(ambiguity, row_candidates)
        known = {
            str(item.get("entity") or item.get("anchor_entity") or "").casefold()
            for item in pointer_rows
        }
        requested = [str(value).strip() for value in model_hint.get("candidates", []) if str(value).strip()]
        validated = [value for value in requested if value.casefold() in known]
        candidates = validated or [
            str(item.get("entity") or item.get("anchor_entity") or "").strip()
            for item in pointer_rows if str(item.get("entity") or item.get("anchor_entity") or "").strip()
        ]
        return {
            "origin": "model_need_focus" if model_hint else "empty_response_fallback",
            "candidates": list(dict.fromkeys(candidates)),
            "candidate_provenance": pointer_rows,
            "bottleneck": str(model_hint.get("bottleneck") or "") or (
                "Resolve the question constraints by comparing the highlighted records with their linked passages."
            ),
            "unvalidated_model_candidates": [value for value in requested if value.casefold() not in known],
            "non_destructive": True,
        }

    @staticmethod
    def _adaptive_protocol() -> str:
        return """\n\nResponse protocol: never return a blank response. If the complete evidence proves one answer, return `FINAL_ANSWER: <shortest answer span>`. Otherwise return `NEED_FOCUS: {\"candidates\":[\"candidate names already in the payload\"],\"bottleneck\":\"missing relation or constraint\"}`. Do not invent candidates or omit evidence."""

    @staticmethod
    def _verification_prompt(question: str, compact_json: str, handoff: dict) -> str:
        return f"""Resolve the question using the same complete, losslessly compressed OUEG evidence payload below.\n\nFocus guidance from the first read (attention only; it does not exclude any graph candidate):\n{json.dumps(handoff, ensure_ascii=False)}\n\nCheck every question constraint against row bindings and linked passages. Return only the shortest final answer span; do not return blank or `None`.\n\nQuestion: {question}\nComplete OUEG payload: {compact_json}\nAnswer:"""

    @staticmethod
    def _source_keys(value: object) -> set[str]:
        """Normalise a HybridQA hyperlink or passage ID for exact joining."""
        raw = str(value or "").strip().casefold()
        if not raw:
            return set()
        bare = raw.removeprefix("passage:").removeprefix("/wiki/")
        return {raw, bare, raw.replace("_", " "), bare.replace("_", " ")}

    def _collision_linked_expansion(
        self, example: DatasetExample, retrieved: dict, ambiguity: dict,
    ) -> dict:
        """Add linked documents for every score-tied table candidate.

        Stage-two retrieval can exhaust its global budget on an early candidate.
        This post-graph expansion is deliberately conditional on a structural
        score tie and covers every tied candidate equally; it never selects a
        winner or deletes context.  It is the evidence-coverage lesson from
        ODYSSEY's hop-wise traversal, adapted to OUEG's non-pruning policy.
        """
        report = {
            "enabled": self.config.use_collision_evidence_expansion,
            "triggered": False,
            "budget": self.config.collision_passage_budget,
            "candidate_rows": [],
            "candidate_entities": [],
            "added_source_ids": [],
            "unresolved_link_targets": [],
        }
        if not self.config.use_collision_evidence_expansion:
            return report
        groups = [
            group for group in ambiguity.get("groups", [])
            if group.get("status") == "SCORE_COLLISION_TIE"
        ]
        if not groups:
            return report
        # Only expand the collision group tied to an explicit question value
        # (e.g. ``21%``). A large table can contain many unrelated duplicate
        # rates; spending the candidate budget on all of them defeats coverage.
        question_terms = self._terms(example.question)
        question_numbers = set(re.findall(r"\d+(?:\.\d+)?", example.question))
        numeric_groups = [
            group for group in groups
            if question_numbers & set(re.findall(r"\d+(?:\.\d+)?", str(group.get("bridge_entity", ""))))
        ]
        relevant_groups = numeric_groups or [
            group for group in groups
            if self._terms(group.get("bridge_entity", "")) & question_terms
        ]
        groups = relevant_groups or groups[:1]
        report["triggered"] = True
        rows: list[tuple[str | None, int]] = []
        seen_rows: set[tuple[str | None, int]] = set()
        entities: list[str] = []
        row_pattern = re.compile(r"^table:(?P<table>.+):row:(?P<row>\d+)$")
        for group in groups:
            for candidate in group.get("candidates", []):
                row_index = candidate.get("row_order_index")
                row_id = str(candidate.get("row_id") or "")
                match = row_pattern.match(row_id)
                if isinstance(row_index, int):
                    row = (match.group("table") if match else None, row_index)
                    if row not in seen_rows:
                        rows.append(row)
                        seen_rows.add(row)
                entity = str(candidate.get("entity") or "").strip()
                if entity:
                    entities.append(entity)
        report["candidate_rows"] = [
            {"table": table_name, "row_index": row_index}
            for table_name, row_index in rows
        ]
        report["candidate_entities"] = list(dict.fromkeys(entities))

        passages = [dict(item) for item in example.text_passages]
        by_key: dict[str, list[dict]] = defaultdict(list)
        for passage in passages:
            for key in self._source_keys(passage.get("id") or passage.get("url")):
                by_key[key].append(passage)
        selected = retrieved.setdefault("text_passages", [])
        selected_keys = {
            key for item in selected
            for key in self._source_keys(item.get("id") or item.get("url"))
        }
        targets: list[str] = []
        for table_name, row_index in rows:
            matching_groups = [
                group for group in example.table_rows
                if table_name is None or str(group.get("table_name", "")) == table_name
            ]
            for group in matching_groups:
                for link in group.get("cell_links", []):
                    if int(link.get("row_index", -1)) == row_index:
                        target = str(link.get("url") or link.get("passage_id") or "").strip()
                        if target:
                            targets.append(target)
        # Some exports omit cell links. An entity-ID match is a conservative
        # fallback that still only exposes an existing supplied passage.
        targets.extend(entities)
        for target in dict.fromkeys(targets):
            matches = [
                passage for key in self._source_keys(target)
                for passage in by_key.get(key, [])
            ]
            matches = list({str(item.get("id") or item.get("url")): item for item in matches}.values())
            if not matches:
                report["unresolved_link_targets"].append(target)
                continue
            for passage in matches:
                passage_id = str(passage.get("id") or passage.get("url"))
                if any(key in selected_keys for key in self._source_keys(passage_id)):
                    continue
                if len(report["added_source_ids"]) >= self.config.collision_passage_budget:
                    return report
                selected.append(dict(passage))
                selected_keys.update(self._source_keys(passage_id))
                report["added_source_ids"].append(passage_id)
        return report

    def _evidence_view(self, retrieved: dict) -> dict:
        """Build the complete OUEG view once, or again after evidence expansion."""
        kg = self.kg_builder.build(retrieved)
        kg_trace = kg.to_trace()
        records = self._complete_subgraph_records(kg_trace, kg.path_edge_records())
        if not self.config.use_record_nodes:
            records = self._without_record_nodes(records)
        compact = deduplicate_edge_contexts(records)
        all_contexts = {
            str(source_id): dict(context)
            for source_id, context in kg.text_contexts.items()
        }
        all_contexts.update(compact["contexts_by_source_id"])
        row_candidates = self._candidate_rows("", records)
        return {
            "kg": kg,
            "kg_trace": kg_trace,
            "records": records,
            "compact": compact,
            "all_contexts": all_contexts,
            "row_candidates": row_candidates,
        }

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        retrieved = two_stage_retrieve(
            example.question, example.table_rows, example.text_passages,
            example.web_snippets, top_k=self.config.top_k,
            second_stage_k=self.config.second_stage_k,
            max_table_rows=self.config.max_table_rows_for_kg,
            use_hyperlink_expansion=self.config.use_hyperlink_expansion,
        )
        view = self._evidence_view(retrieved)
        kg = view["kg"]
        kg_trace = view["kg_trace"]
        records = view["records"]
        compact = view["compact"]
        all_contexts = view["all_contexts"]
        row_candidates = self._candidate_rows(example.question, records)
        ambiguity = self._ambiguity_assessment(example.question, row_candidates)
        collision_expansion = self._collision_linked_expansion(example, retrieved, ambiguity)
        if collision_expansion["added_source_ids"]:
            view = self._evidence_view(retrieved)
            kg = view["kg"]
            kg_trace = view["kg_trace"]
            records = view["records"]
            compact = view["compact"]
            all_contexts = view["all_contexts"]
            row_candidates = self._candidate_rows(example.question, records)
            ambiguity = self._ambiguity_assessment(example.question, row_candidates)
        seed_candidates = self._seed_expansion_paths(example.question, records)
        if not self.config.use_lexical_tiebreak:
            for path in [*row_candidates, *seed_candidates]:
                path.pop("lexical_overlap_with_bridge_entity", None)
                path["presentation_score"] = path.get("score", 0.0)
        ordering_hint, ordered_rows = self._ordering_hint(example.question, row_candidates)
        # Row bundles are always complete. DFS paths are an additional view of
        # the same union graph and have only a fixed, non-score safety cap.
        suggested_paths = [*ordered_rows, *sorted(
            seed_candidates,
            key=lambda path: (-float(path.get("presentation_score", path.get("score", 0.0))), str(path["path_id"])),
        )]
        if not self.config.use_path_guidance:
            suggested_paths = []
            ordering_hint = {
                "detected_signal": "disabled",
                "note": "Path guidance ablation: answer from the complete subgraph only.",
            }
        annotated_nodes = self._annotated_subgraph_nodes(
            kg_trace, records, suggested_paths,
            include_trace_topology=self.config.use_record_nodes,
        )
        path_generation = {
            "enabled": self.config.use_path_guidance,
            "row_bundle": "Every has_record row is emitted; no top-k or score threshold is applied." if self.config.use_path_guidance else "disabled",
            "seed_expansion": {
                "target_entity_type": self._target_entity_type(example.question),
                "max_enumerated": 50,
                "max_hops": 5,
                "includes_text_edges": True,
                "linked_passage_is_terminal": False,
            },
            "scoring": "All score_components are metadata used only to prioritize reading order; they never determine candidate inclusion.",
        }
        prompt_ambiguity = deepcopy(ambiguity)
        if not self.config.use_lexical_tiebreak:
            for group in prompt_ambiguity.get("groups", []):
                group.pop("lexical_tiebreak", None)
                for candidate in group.get("candidates", []):
                    candidate.pop("lexical_overlap_with_bridge_entity", None)
            prompt_ambiguity.get("selective_prediction", {}).pop("lexical_tiebreak_winner", None)
            prompt_ambiguity.get("selective_prediction", {}).pop("lexical_tiebreak_path_id", None)
        # Keep this full payload unchanged for audit. The LLM receives the
        # compact serialization built below, which has the same edge union.
        payload = {
            "subgraph": {
                "nodes": annotated_nodes,
                "kg_edges": compact["edges"],
                "text_contexts": [all_contexts[key] for key in sorted(all_contexts)],
            },
            "suggested_paths": suggested_paths,
            "ordering_hint": ordering_hint,
            "ambiguity": ambiguity,
            "path_generation": path_generation,
        }
        tie_break_hint = ""
        if self.config.use_lexical_tiebreak and ambiguity["status"] == "SCORE_COLLISION_TIE":
            tie_break_hint = (
                "\n\nWarning: More than one candidate satisfies the same bridge condition. "
                "Prefer an entity whose name overlaps with the place-name tokens or is directly "
                "present in the cross-referenced context, but treat this only as a weak tie-break "
                "and do not discard other valid candidates."
            )
        compressed_prompt = self.prompt_builder.build(
            question=example.question,
            records=records,
            contexts_by_source_id=all_contexts,
            suggested_paths=suggested_paths,
            ordering_hint=ordering_hint,
            ambiguity=prompt_ambiguity,
            path_generation=path_generation,
        )
        prompt = self.prompt_builder.prompt(
            question=example.question,
            compact_json=compressed_prompt["json"],
            tie_break_hint=tie_break_hint,
        )
        if self.config.use_adaptive_verification:
            prompt += self._adaptive_protocol()
        provider = get_provider()
        request_max_tokens = self._request_token_limit(provider, self.config.max_output_tokens)
        retry_prompt = None
        adaptive_verification = {
            "enabled": self.config.use_adaptive_verification,
            "triggered": False,
            "first_response": None,
            "handoff": None,
            "second_response": None,
            "final_decision": "not_run",
        }
        abstained = False
        llm_calls = 0
        if ambiguity["is_ambiguous"] and self.config.ambiguity_policy == "return_candidates":
            answer = self._ambiguous_answer(ambiguity)
            abstained = True
        elif (
            self.config.use_lexical_tiebreak
            and ambiguity["is_ambiguous"]
            and self.config.ambiguity_policy == "lexical_tiebreak"
            and ambiguity["selective_prediction"]["lexical_tiebreak_is_safe"]
        ):
            answer = str(ambiguity["selective_prediction"]["lexical_tiebreak_winner"])
        else:
            first_response = llm_call(prompt, max_tokens=request_max_tokens, temperature=self.config.temperature)
            llm_calls = 1
            if self.config.use_adaptive_verification:
                answer, model_hint = self._parse_adaptive_response(first_response)
                adaptive_verification["first_response"] = str(first_response or "")
                if answer:
                    adaptive_verification["final_decision"] = "fast_path_answer"
                else:
                    handoff = self._focus_handoff(model_hint, ambiguity, row_candidates)
                    retry_prompt = self._verification_prompt(
                        example.question, compressed_prompt["json"], handoff,
                    )
                    adaptive_verification["triggered"] = True
                    adaptive_verification["handoff"] = handoff
                    second_response = llm_call(
                        retry_prompt, max_tokens=request_max_tokens,
                        temperature=self.config.temperature,
                    )
                    answer = self._short_answer(second_response)
                    adaptive_verification["second_response"] = str(second_response or "")
                    adaptive_verification["final_decision"] = (
                        "verified_after_focus" if answer else "grounded_abstention"
                    )
                    llm_calls = 2
            else:
                answer = self._short_answer(first_response)
                if not answer:
                    retry_prompt = prompt + "\n\nYour previous response was empty. Return the shortest non-empty answer span now.\nAnswer:"
                    answer = self._short_answer(llm_call(retry_prompt, max_tokens=request_max_tokens, temperature=self.config.temperature))
                    llm_calls = 2
                llm_calls = 2
        retrieval_trace = dict(retrieved.get("retrieval_trace", {}))
        retrieval_trace["collision_evidence_expansion"] = collision_expansion
        return {
            "answer": answer,
            "method": self.method_name,
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "kg_summary": kg.summary(),
            "full_kg": kg_trace,
            "oueg_payload": payload,
            "compact_oueg_payload": compressed_prompt["payload"],
            "prompt_compression": compressed_prompt["stats"],
            "suggested_paths": suggested_paths,
            "ordering_hint": ordering_hint,
            "ambiguity": ambiguity,
            "ambiguity_policy": self.config.ambiguity_policy,
            "abstained_for_ambiguity": abstained,
            "adaptive_verification": adaptive_verification,
            "collision_evidence_expansion": collision_expansion,
            "entity_anchor": retrieved.get("retrieval_trace", {}).get("entity_anchor", {}),
            "retrieval_trace": retrieval_trace,
            "retrieved_passage_ids": [
                str(item.get("id") or item.get("url"))
                for item in retrieved.get("text_passages", [])
                if item.get("id") or item.get("url")
            ],
            "prompt": prompt,
            "prompt_chars": len(prompt),
            "request_max_output_tokens": request_max_tokens,
            "answer_retry_attempted": retry_prompt is not None,
            "retry_prompt": retry_prompt,
            "retry_prompt_chars": len(retry_prompt) if retry_prompt else 0,
            "llm_calls": llm_calls,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
