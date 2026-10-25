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
from src.baselines.rag_variants import RAGConfig, rank_documents
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
        answer = re.sub(r"^(?:final[ _]+)?answer\s*:\s*", "", answer, flags=re.I)
        answer = answer.strip().strip("`\"'").strip()
        return "" if answer.casefold().strip(" .") in {"", "none", "unknown", "n/a", "na", "null"} else answer

    def _answer_time_evidence(
        self,
        records: list[dict],
        contexts_by_source_id: dict[str, dict],
        suggested_paths: list[dict],
    ) -> tuple[list[dict], dict[str, dict], list[dict], dict]:
        """Return a bounded grounded reader view; the full KG remains audited.

        Serializing the complete union graph proved counterproductive for the
        20B reader: it had to search hundreds of irrelevant records in one
        call.  The existing path scores are reader priorities, so retain their
        top grounded paths and every context they reference.
        """
        if not self.config.use_path_focused_prompt:
            return records, contexts_by_source_id, suggested_paths, {
                "enabled": False,
                "full_record_count": len(records),
                "selected_record_count": len(records),
                "full_context_count": len(contexts_by_source_id),
                "selected_context_count": len(contexts_by_source_id),
                "selected_path_ids": [path.get("path_id") for path in suggested_paths],
            }

        # Table row bundles are the complete structural candidate set.  Keep
        # all of them so path focus cannot silently discard a valid table
        # binding; apply the budget only to exploratory text/seed paths.
        row_paths = [
            path for path in suggested_paths
            if path.get("path_kind") == "row_bundle"
        ]
        ranked_expansion_paths = sorted(
            [path for path in suggested_paths if path.get("path_kind") != "row_bundle"],
            key=lambda path: (
                -float(path.get("presentation_score", path.get("score", 0.0))),
                str(path.get("path_id", "")),
            ),
        )
        selected_paths = [
            *row_paths,
            *ranked_expansion_paths[:self.config.prompt_path_budget],
        ]
        selected_edge_ids = {
            str(edge_id)
            for path in selected_paths
            for edge_id in path.get("edge_ids", [])
            if edge_id is not None
        }
        selected_records = [
            record for record in records
            if str(record.get("edge_id")) in selected_edge_ids
        ]
        # Do not turn a malformed path guide into an empty reader payload.
        if not selected_records:
            selected_records = records
            selected_paths = suggested_paths

        context_ids = {
            str(source_id)
            for record in selected_records
            for source_id in (record.get("context_ids") or [])
            if source_id
        }
        context_ids.update(
            str(context.get("source_id"))
            for record in selected_records
            for context in record.get("contexts", [])
            if context.get("source_id")
        )
        # Linked-passage edges identify their context in the tail, rather than
        # in an inline context list.
        context_ids.update(
            str(record.get("tail", "")).removeprefix("passage:")
            for record in selected_records
            if str(record.get("tail", "")).startswith("passage:")
        )
        selected_contexts = {
            source_id: context
            for source_id, context in contexts_by_source_id.items()
            if str(source_id) in context_ids
        }
        return selected_records, selected_contexts, selected_paths, {
            "enabled": True,
            "path_budget": self.config.prompt_path_budget,
            "retained_row_bundle_count": len(row_paths),
            "retained_expansion_path_count": min(
                len(ranked_expansion_paths), self.config.prompt_path_budget,
            ),
            "full_record_count": len(records),
            "selected_record_count": len(selected_records),
            "full_context_count": len(contexts_by_source_id),
            "selected_context_count": len(selected_contexts),
            "selected_path_ids": [path.get("path_id") for path in selected_paths],
        }

    @classmethod
    def _parse_adaptive_response(cls, raw: str) -> tuple[str, dict]:
        """Parse an answer or a diagnostic focus handoff from a reader call.

        The parser deliberately accepts a plain non-empty span for backwards
        compatibility with models that ignore the protocol.  A malformed or
        empty response is not silently promoted to a guessed answer.
        """
        text = str(raw or "").strip()
        answer_match = re.search(r"FINAL[ _]+ANSWER\s*:\s*(.+)", text, re.I)
        answer = cls._short_answer(answer_match.group(1) if answer_match else "")
        if answer_match:
            return answer, {}
        unresolved = bool(re.search(r"UNRESOLVED\s*:", text, re.I))
        needs_focus = bool(re.search(r"NEED_FOCUS\s*:", text, re.I))
        if not needs_focus and not unresolved:
            plain = cls._short_answer(text)
            return plain, {}

        hint = {
            "raw": text,
            "response_type": "unresolved" if unresolved else "need_focus",
            "candidates": [],
            "bottleneck": "",
            "blocker_type": "",
            "needed_check": "",
        }
        json_match = re.search(
            r"(?:NEED_FOCUS|UNRESOLVED)\s*:\s*(\{.*\})", text, re.I | re.S,
        )
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                values = parsed.get("candidates", [])
                hint["candidates"] = values if isinstance(values, list) else [values]
                hint["bottleneck"] = str(parsed.get("bottleneck") or parsed.get("reason") or "")
                hint["blocker_type"] = str(parsed.get("blocker_type") or "")
                hint["needed_check"] = str(parsed.get("needed_check") or "")
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
    def _evidence_path_audit(raw: str, allowed_refs: set[str]) -> dict:
        """Extract model-selected evidence IDs and reject IDs outside its prompt."""
        match = re.search(r"EVIDENCE_PATH\s*:\s*(\{.*?\}|\[.*?\])", str(raw or ""), re.I | re.S)
        if match is None:
            return {"required": True, "provided": False, "selected_refs": [], "invalid_refs": []}
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            return {"required": True, "provided": True, "selected_refs": [], "invalid_refs": [match.group(1)]}
        if isinstance(value, dict):
            refs = [item for items in value.values() for item in (items if isinstance(items, list) else [items])]
        else:
            refs = value if isinstance(value, list) else [value]
        rendered = [str(item) for item in refs if str(item).strip()]
        return {
            "required": True,
            "provided": True,
            "selected_refs": [item for item in rendered if item in allowed_refs],
            "invalid_refs": [item for item in rendered if item not in allowed_refs],
        }

    @staticmethod
    def _serialized_evidence_refs(serialized: str) -> set[str]:
        """Collect compact/raw edge and passage IDs that are visible to a reader."""
        return set(re.findall(r"(?:\be\d+\b|\bp\d+\b|\bkg:\d+\b|/wiki/[A-Za-z0-9_()'.,%\-]+)", serialized))

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

    @staticmethod
    def _is_low_information_focus(value: object) -> bool:
        text = str(value or "").strip()
        return not text or bool(re.fullmatch(r"[#№]?\s*\d+(?:[.,]\d+)?(?:st|nd|rd|th)?", text, re.I))

    @staticmethod
    def _path_values(path: dict) -> list[str]:
        values = []
        for value in path.get("sort_keys", {}).values():
            values.extend(value if isinstance(value, list) else [value])
        values.append(path.get("bridge_entity"))
        return [str(value).strip() for value in values if str(value or "").strip()]

    def _diagnostic_focus_rows(
        self, question: str, model_hint: dict, row_candidates: list[dict],
    ) -> list[dict]:
        """Ground an L1 diagnostic in table values, never in a default column.

        A row anchor can be a rank or year because of table column order.  L1
        often names the useful entity in ``needed_check`` instead; resolve that
        mention against already-grounded row values before retrieving text.
        """
        diagnostic = " ".join(str(model_hint.get(key) or "") for key in (
            "needed_check", "bottleneck",
        )).casefold()
        requested = [str(value).strip() for value in model_hint.get("candidates", []) if str(value).strip()]
        selected: list[tuple[dict, str, int]] = []
        for path in row_candidates:
            matches = []
            for value in self._path_values(path):
                if self._is_low_information_focus(value):
                    continue
                lowered = value.casefold()
                if lowered in diagnostic or any(lowered == item.casefold() for item in requested):
                    matches.append(value)
            if matches:
                entity = max(matches, key=len)
                selected.append((path, entity, len(entity)))
        # Explicit ordinal questions have a deterministic row binding even if
        # the L1 prose names only the derived entity (e.g. tenth metro area).
        ordinal = _ordinal_rank(question)
        if ordinal is not None:
            for path in row_candidates:
                if path.get("row_order_index") != ordinal - 1:
                    continue
                options = [
                    value for value in self._path_values(path)
                    if not self._is_low_information_focus(value)
                ]
                if options:
                    selected.append((path, max(options, key=len), 1))
        if not selected:
            return []
        # One row can match multiple diagnostic strings; retain its strongest
        # non-numeric entity and no more than three grounded focus rows.
        by_row: dict[str, tuple[dict, str, int]] = {}
        for path, entity, strength in selected:
            row_id = str(path.get("row_id") or path.get("path_id"))
            if row_id not in by_row or strength > by_row[row_id][2]:
                by_row[row_id] = (path, entity, strength)
        return [
            {
                "entity": entity,
                "row_id": path.get("row_id"),
                "row_order_index": path.get("row_order_index"),
                "bridge_entity": path.get("bridge_entity"),
                "path_id": path.get("path_id"),
                "row_binding": path.get("sort_keys", {}),
            }
            for path, entity, _ in sorted(
                by_row.values(), key=lambda item: (-item[2], str(item[0].get("path_id")))
            )[:3]
        ]

    def _focus_handoff(
        self, question: str, model_hint: dict, ambiguity: dict, row_candidates: list[dict],
    ) -> dict:
        """Validate model hints against graph candidates, then add a local fallback.

        Hints never determine which evidence is serialized in the verification
        prompt.  They only make a few already-present candidate records easier
        for the reader to locate.
        """
        pointer_rows = (
            self._diagnostic_focus_rows(question, model_hint, row_candidates)
            if self.config.use_diagnostic_focus_resolution else []
        ) or self._focus_candidate_rows(ambiguity, row_candidates)
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
        # Scores and lexical features are useful for L1 ordering, but are not
        # evidence.  Do not anchor the L2 reader on them.
        safe_provenance = [
            {
                key: item.get(key)
                for key in ("entity", "anchor_entity", "row_id", "row_order_index", "bridge_entity", "path_id")
                if item.get(key) is not None
            }
            for item in pointer_rows
        ]
        return {
            "origin": (
                "model_unresolved" if model_hint.get("response_type") == "unresolved"
                else "model_need_focus" if model_hint
                else "empty_model_response"
            ),
            "candidates": list(dict.fromkeys(candidates)),
            "candidate_provenance": safe_provenance,
            "focus_rows": safe_provenance,
            "blocker_type": str(model_hint.get("blocker_type") or (
                "empty_model_response" if not model_hint else "unspecified"
            )),
            "bottleneck": str(model_hint.get("bottleneck") or "") or (
                "Resolve the question constraints by comparing the highlighted records with their linked passages."
            ),
            "needed_check": str(model_hint.get("needed_check") or "") or (
                "Check the highlighted row bindings and linked passages for the unresolved question constraint."
            ),
            "unvalidated_model_candidates": [value for value in requested if value.casefold() not in known],
            "non_destructive": True,
        }

    @staticmethod
    def _adaptive_protocol() -> str:
        return """\n\nResponse protocol: never return a blank response. Return exactly one of these forms:\n1. `FINAL_ANSWER: <shortest answer span>\nEVIDENCE_PATH: {\"edges\":[\"edge IDs from the payload\"],\"passages\":[\"passage IDs from the payload\"]}` when the evidence proves one answer. Cite at least one supplied edge or passage ID.\n2. `NEED_FOCUS: {\"candidates\":[\"candidate names already in the payload\"],\"blocker_type\":\"candidate_collision|missing_link|conflicting_evidence|answer_type_uncertain\",\"bottleneck\":\"why the answer is not yet unique\",\"needed_check\":\"exact row, relation, year, rank, or passage fact to compare\"}` when a focused re-read can resolve it.\n3. `UNRESOLVED: {\"blocker_type\":\"missing_link|insufficient_evidence|conflicting_evidence\",\"bottleneck\":\"what evidence is absent or contradictory\",\"needed_check\":\"what fact would be required\"}` when this payload cannot prove an answer.\nDo not invent candidates or evidence."""

    @staticmethod
    def _verification_prompt(question: str, compact_json: str, handoff: dict, *, mode: str) -> str:
        if mode == "delta_only":
            return f"""Resolve the question using only the grounded L2 state capsule below. This is a new request: do not assume you remember L1 or use facts absent from this capsule.\n\nThe capsule contains the original question, the unresolved constraint, complete row bindings for the focus candidates, and their relevant evidence. `coverage` says whether retrieval found new text; absence of evidence is not a negative fact. Scores are intentionally omitted.\n\nReturn `FINAL_ANSWER: <shortest evidence span>\nEVIDENCE_PATH: {{\"edges\":[\"edge IDs in this capsule\"],\"passages\":[\"source IDs in this capsule\"]}}` only if exactly one candidate is proven. Cite at least one supplied ID. Otherwise return `UNRESOLVED: {{\"blocker_type\":\"...\",\"bottleneck\":\"...\",\"needed_check\":\"...\"}}`. Never return blank or invent evidence.\n\nQuestion: {question}\nL2 state capsule: {compact_json}\nAnswer:"""
        return f"""Resolve the question using the complete grounded OUEG evidence payload below.\n\nFocus guidance from the first read (attention only; it does not exclude any graph candidate or evidence in this payload):\n{json.dumps(handoff, ensure_ascii=False)}\n\nCheck the stated needed_check against row bindings and linked passages. Copy the shortest answer span exactly as it appears in the evidence; do not translate or expand a name. Never return blank: use `FINAL_ANSWER: <span>` if proven, otherwise return `UNRESOLVED: {{\"blocker_type\":\"...\",\"bottleneck\":\"...\",\"needed_check\":\"...\"}}`.\n\nQuestion: {question}\nComplete grounded OUEG payload: {compact_json}\nAnswer:"""

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

    @staticmethod
    def _record_source_ids(record: dict) -> set[str]:
        """Return all source IDs referenced by a compact OUEG record."""
        values = set(str(value) for value in record.get("context_ids", []) if value)
        values.update(
            str(context.get("source_id"))
            for context in record.get("contexts", [])
            if context.get("source_id")
        )
        tail = str(record.get("tail") or "")
        if tail.startswith("passage:"):
            values.add(tail.removeprefix("passage:"))
        return values

    def _focus_evidence_augmentation(
        self, example: DatasetExample, retrieved: dict, handoff: dict,
    ) -> dict:
        """Retrieve missing candidate-linked passages for L2, symmetrically.

        This is deliberately not a new answer-selection stage.  It may only
        add user-supplied passages linked to *each* validated focus candidate;
        it cannot remove first-read evidence or pick a winner.
        """
        blocker_type = str(handoff.get("blocker_type") or "").casefold()
        eligible = {"missing_link", "insufficient_evidence"}
        report = {
            "enabled": self.config.use_focus_evidence_augmentation,
            "triggered": False,
            "reason": blocker_type,
            "per_candidate_budget": self.config.focus_passage_budget_per_candidate,
            "query_fallback_budget": self.config.focus_query_fallback_budget,
            "candidate_sources": {},
            "linked_source_ids": {},
            "query_source_ids": {},
            "added_source_ids": [],
            "unresolved_candidates": [],
        }
        if not self.config.use_focus_evidence_augmentation or blocker_type not in eligible:
            return report
        candidates = [str(value).strip() for value in handoff.get("candidates", []) if str(value).strip()]
        if not candidates:
            return report
        report["triggered"] = True
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
        # Map candidate entities and *grounded focus rows* to their links.
        # The latter matters when the physical row anchor is a Rank/Year cell.
        links_by_entity: dict[str, list[str]] = defaultdict(list)
        links_by_focus_row: dict[str, list[str]] = defaultdict(list)
        row_pattern = re.compile(r"^table:(?P<table>.+):row:(?P<row>\d+)$")
        focus_row_keys: dict[tuple[str | None, int], list[str]] = defaultdict(list)
        for focus in handoff.get("focus_rows", []):
            match = row_pattern.match(str(focus.get("row_id") or ""))
            row_index = focus.get("row_order_index")
            if isinstance(row_index, int):
                focus_row_keys[(match.group("table") if match else None, row_index)].append(
                    str(focus.get("entity") or ""),
                )
        for group in example.table_rows:
            table_name = str(group.get("table_name") or "")
            for link in group.get("cell_links", []):
                row_index = link.get("row_index")
                column = str(link.get("column_name") or "")
                if not isinstance(row_index, int):
                    continue
                rows = group.get("rows", [])
                if row_index < 0 or row_index >= len(rows):
                    continue
                entity = str(rows[row_index].get(column) or "").strip()
                target = str(link.get("url") or link.get("passage_id") or "").strip()
                if entity and target:
                    links_by_entity[entity.casefold()].append(target)
                    for focus_entity in focus_row_keys.get((table_name, row_index), []) + focus_row_keys.get((None, row_index), []):
                        if focus_entity:
                            links_by_focus_row[focus_entity.casefold()].append(target)
        for candidate in dict.fromkeys(candidates):
            targets = [
                *links_by_focus_row.get(candidate.casefold(), []),
                *links_by_entity.get(candidate.casefold(), []),
                candidate,
            ]
            matches: list[dict] = []
            seen_match_ids: set[str] = set()
            for target in dict.fromkeys(targets):
                for key in self._source_keys(target):
                    for passage in by_key.get(key, []):
                        passage_id = str(passage.get("id") or passage.get("url"))
                        if passage_id and passage_id not in seen_match_ids:
                            matches.append(passage)
                            seen_match_ids.add(passage_id)
            linked_match_ids = [str(item.get("id") or item.get("url")) for item in matches]
            # If links are absent or unrelated, search only the supplied
            # example corpus with a grounded entity + diagnostic query.
            query = " ".join((
                example.question, candidate, str(handoff.get("needed_check") or ""),
            ))
            ranked = rank_documents(
                query,
                [{"id": str(item.get("id") or item.get("url")), "text": str(item.get("text") or "")}
                 for item in passages],
                self.config.focus_query_fallback_budget,
            )
            query_matches = [
                next((item for item in passages if str(item.get("id") or item.get("url")) == ranked_item["id"]), None)
                for ranked_item in ranked
            ]
            query_matches = [item for item in query_matches if item is not None]
            added_for_candidate: list[str] = []
            query_added: list[str] = []
            for passage, origin in [
                *((passage, "linked") for passage in matches),
                *((passage, "query") for passage in query_matches),
            ]:
                if len(added_for_candidate) >= self.config.focus_passage_budget_per_candidate:
                    break
                passage_id = str(passage.get("id") or passage.get("url"))
                if any(key in selected_keys for key in self._source_keys(passage_id)):
                    continue
                selected.append(dict(passage))
                selected_keys.update(self._source_keys(passage_id))
                added_for_candidate.append(passage_id)
                report["added_source_ids"].append(passage_id)
                if origin == "query":
                    query_added.append(passage_id)
            report["candidate_sources"][candidate] = added_for_candidate
            report["linked_source_ids"][candidate] = linked_match_ids
            report["query_source_ids"][candidate] = query_added
            if not matches and not query_matches:
                report["unresolved_candidates"].append(candidate)
        return report

    def _semantic_delta(
        self, records: list[dict], added_source_ids: list[str], candidates: list[str],
    ) -> list[dict]:
        """Expose newly retrieved grounded facts as a small L2 attention card."""
        added_keys = {
            key for source_id in added_source_ids for key in self._source_keys(source_id)
        }
        candidate_keys = {str(candidate).casefold() for candidate in candidates}
        delta = []
        for record in records:
            source_match = any(
                key in added_keys
                for source_id in self._record_source_ids(record)
                for key in self._source_keys(source_id)
            )
            entity_match = str(record.get("head") or "").casefold() in candidate_keys
            if not source_match and not entity_match:
                continue
            delta.append({
                key: record.get(key)
                for key in ("edge_id", "head", "relation", "tail", "context_ids")
                if record.get(key) is not None
            })
        # This is only an orientation aid: the full rebuilt graph remains the
        # source of truth, so cap the card rather than selecting an answer.
        return delta[:24]

    def _l2_existing_witnesses(
        self, question: str, handoff: dict, l1_contexts: dict[str, dict],
    ) -> list[str]:
        """Retain a few L1 passages that directly answer the missing check."""
        if not l1_contexts:
            return []
        query = " ".join((
            question,
            str(handoff.get("needed_check") or ""),
            *[str(value) for value in handoff.get("candidates", [])],
        ))
        ranked = rank_documents(
            query,
            [
                {"id": source_id, "text": str(context.get("text") or "")}
                for source_id, context in l1_contexts.items()
            ],
            self.config.l2_existing_witness_budget,
        )
        return [str(item["id"]) for item in ranked]

    @staticmethod
    def _l2_record(record: dict) -> dict:
        """Serialize an evidence edge without reader-priority metadata."""
        return {
            key: record.get(key)
            for key in ("edge_id", "head", "relation", "tail", "context_ids")
            if record.get(key) is not None
        }

    @classmethod
    def _l2_excerpt(cls, text: object, candidate: str, needed_check: str, max_chars: int) -> str:
        """Keep only local sentence evidence; do not ask another model to trim it."""
        value = str(text or "").strip()
        if len(value) <= max_chars:
            return value
        terms = cls._terms(candidate) | cls._terms(needed_check)
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", value) if item.strip()]
        ranked = sorted(
            range(len(sentences)),
            key=lambda index: (-len(cls._terms(sentences[index]) & terms), index),
        )
        chosen: list[str] = []
        used = 0
        for index in ranked:
            sentence = sentences[index]
            if not (cls._terms(sentence) & terms):
                continue
            if used + len(sentence) + 1 > max_chars:
                continue
            chosen.append(sentence)
            used += len(sentence) + 1
            if len(chosen) >= 3:
                break
        return " ".join(chosen) or value[:max_chars]

    def _l2_state_capsule(
        self,
        *,
        question: str,
        handoff: dict,
        row_candidates: list[dict],
        records: list[dict],
        contexts_by_source_id: dict[str, dict],
        augmentation: dict,
        existing_witness_source_ids: list[str],
    ) -> dict:
        """Build the small sufficient context passed from L1 to an L2 reader.

        L2 calls are stateless.  This capsule therefore repeats the minimal
        row constraints plus evidence needed to resolve the L1 diagnostic,
        rather than assuming the model can remember the large L1 OUEG prompt.
        """
        candidates = [str(value) for value in handoff.get("candidates", [])]
        candidate_lookup = {
            str(item.get("anchor_entity") or "").casefold(): item
            for item in row_candidates
        }
        rows_by_id = {str(item.get("row_id") or ""): item for item in row_candidates}
        for focus in handoff.get("focus_rows", []):
            entity = str(focus.get("entity") or "").casefold()
            row = rows_by_id.get(str(focus.get("row_id") or ""))
            if entity and row is not None:
                candidate_lookup[entity] = row
        candidate_sources = dict(augmentation.get("candidate_sources", {}))
        packets = []
        for entity in candidates:
            path = candidate_lookup.get(entity.casefold(), {})
            source_ids = list(candidate_sources.get(entity, []))
            # Existing linked evidence is needed for collision/comparison
            # diagnostics even when no new retrieval was eligible.
            for record in records:
                if str(record.get("head") or "").casefold() != entity.casefold():
                    continue
                source_ids.extend(self._record_source_ids(record))
            source_ids = list(dict.fromkeys(source_id for source_id in source_ids if source_id))
            source_keys = {
                key for source_id in source_ids for key in self._source_keys(source_id)
            }
            path_edge_ids = {str(value) for value in path.get("edge_ids", []) if value is not None}
            evidence = []
            used_edge_ids: set[str] = set()
            for record in records:
                record_id = str(record.get("edge_id") or "")
                touches_entity = (
                    str(record.get("head") or "").casefold() == entity.casefold()
                    or str(record.get("tail") or "").casefold() == entity.casefold()
                )
                touches_source = any(
                    key in source_keys
                    for source_id in self._record_source_ids(record)
                    for key in self._source_keys(source_id)
                )
                if not (record_id in path_edge_ids or touches_entity or touches_source):
                    continue
                if record_id in used_edge_ids or len(evidence) >= self.config.l2_max_edges_per_candidate:
                    continue
                evidence.append(self._l2_record(record))
                used_edge_ids.add(record_id)
            passages = []
            for source_id in source_ids[:self.config.l2_max_contexts_per_candidate]:
                context = contexts_by_source_id.get(str(source_id))
                if context is None:
                    continue
                passages.append({
                    "source_id": source_id,
                    "text": self._l2_excerpt(
                        context.get("text", ""), entity, str(handoff.get("needed_check") or ""),
                        self.config.l2_context_snippet_chars,
                    ),
                })
            packets.append({
                "entity": entity,
                "row_id": path.get("row_id"),
                "row_binding": path.get("sort_keys", {}),
                "evidence": evidence,
                "passages": passages,
                "retrieval_coverage": (
                    "new_linked_evidence" if candidate_sources.get(entity)
                    else "no_new_linked_evidence"
                ),
            })
        witnesses = []
        for source_id in existing_witness_source_ids:
            context = contexts_by_source_id.get(source_id)
            if context is None:
                continue
            witnesses.append({
                "source_id": source_id,
                "text": self._l2_excerpt(
                    context.get("text", ""), " ".join(candidates),
                    str(handoff.get("needed_check") or ""), self.config.l2_context_snippet_chars,
                ),
            })
        return {
            "format": "oueg-l2-state-capsule-v1",
            "question": question,
            "l1_diagnostic": {
                key: handoff.get(key)
                for key in ("blocker_type", "bottleneck", "needed_check")
            },
            "candidate_packets": packets,
            "l1_witnesses": witnesses,
            "coverage": {
                "augmentation_triggered": augmentation.get("triggered", False),
                "added_source_ids": augmentation.get("added_source_ids", []),
                "unresolved_candidates": augmentation.get("unresolved_candidates", []),
            },
        }

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
        answer_records, answer_contexts, answer_paths, answer_evidence_audit = self._answer_time_evidence(
            records, all_contexts, suggested_paths,
        )
        # Preserve only a later-ranked subset of these L1-visible contexts for
        # the small L2 packet; do not assume a fresh API call remembers them.
        l1_contexts = dict(answer_contexts)
        compressed_prompt = self.prompt_builder.build(
            question=example.question,
            records=answer_records,
            contexts_by_source_id=answer_contexts,
            suggested_paths=answer_paths,
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
        verification_evidence = None
        focus_evidence_augmentation = None
        adaptive_verification = {
            "enabled": self.config.use_adaptive_verification,
            "triggered": False,
            "first_response": None,
            "handoff": None,
            "second_response": None,
            "final_decision": "not_run",
        }
        answer_evidence_path = None
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
                first_evidence_path = self._evidence_path_audit(
                    first_response, self._serialized_evidence_refs(compressed_prompt["json"]),
                )
                adaptive_verification["first_evidence_path"] = first_evidence_path
                if answer:
                    answer_evidence_path = first_evidence_path
                    adaptive_verification["final_decision"] = "fast_path_answer"
                else:
                    handoff = self._focus_handoff(
                        example.question, model_hint, ambiguity, row_candidates,
                    )
                    existing_witness_source_ids = self._l2_existing_witnesses(
                        example.question, handoff, l1_contexts,
                    )
                    handoff["existing_witness_source_ids"] = existing_witness_source_ids
                    focus_evidence_augmentation = self._focus_evidence_augmentation(
                        example, retrieved, handoff,
                    )
                    if focus_evidence_augmentation["added_source_ids"]:
                        # Rebuild, rather than append text to the old prompt:
                        # added passages can contribute new grounded triples,
                        # links, and contexts to the OUEG.
                        augmented_view = self._evidence_view(retrieved)
                        kg = augmented_view["kg"]
                        kg_trace = augmented_view["kg_trace"]
                        records = augmented_view["records"]
                        compact = augmented_view["compact"]
                        all_contexts = augmented_view["all_contexts"]
                        handoff["semantic_delta"] = self._semantic_delta(
                            records,
                            focus_evidence_augmentation["added_source_ids"],
                            handoff["candidates"],
                        )
                    handoff["evidence_augmentation"] = focus_evidence_augmentation
                    if self.config.l2_evidence_mode == "delta_only":
                        state_capsule = self._l2_state_capsule(
                            question=example.question,
                            handoff=handoff,
                            row_candidates=row_candidates,
                            records=records,
                            contexts_by_source_id=all_contexts,
                            augmentation=focus_evidence_augmentation,
                            existing_witness_source_ids=existing_witness_source_ids,
                        )
                        verification_json = json.dumps(
                            state_capsule, ensure_ascii=False, separators=(",", ":"),
                        )
                        adaptive_verification["l2_state_capsule"] = state_capsule
                        verification_evidence = {
                            "mode": "delta_only",
                            "augmentation_applied": bool(focus_evidence_augmentation["added_source_ids"]),
                            "full_record_count": len(records),
                            "full_context_count": len(all_contexts),
                            "l2_record_count": sum(
                                len(packet["evidence"])
                                for packet in state_capsule["candidate_packets"]
                            ),
                            "l2_context_count": sum(
                                len(packet["passages"])
                                for packet in state_capsule["candidate_packets"]
                            ) + len(state_capsule["l1_witnesses"]),
                            "payload_chars": len(verification_json),
                        }
                    else:
                        # Diagnostic ablation: restore all evidence after a
                        # focused first read, retaining the old full re-read.
                        verification_payload = self.prompt_builder.build(
                            question=example.question,
                            records=records,
                            contexts_by_source_id=all_contexts,
                            suggested_paths=suggested_paths,
                            ordering_hint=ordering_hint,
                            ambiguity=prompt_ambiguity,
                            path_generation=path_generation,
                        )
                        verification_json = verification_payload["json"]
                        verification_evidence = {
                            "mode": "complete_re_read",
                            "augmentation_applied": bool(focus_evidence_augmentation["added_source_ids"]),
                            "full_record_count": len(records),
                            "full_context_count": len(all_contexts),
                            "first_read_record_count": len(answer_records),
                            "first_read_context_count": len(answer_contexts),
                            "all_edges_represented": verification_payload["stats"].get(
                                "all_edges_represented", False,
                            ),
                            "payload_chars": len(verification_json),
                        }
                    retry_prompt = self._verification_prompt(
                        example.question, verification_json, handoff,
                        mode=self.config.l2_evidence_mode,
                    )
                    adaptive_verification["triggered"] = True
                    adaptive_verification["handoff"] = handoff
                    second_response = llm_call(
                        retry_prompt, max_tokens=request_max_tokens,
                        temperature=self.config.temperature,
                    )
                    answer, second_diagnostic = self._parse_adaptive_response(second_response)
                    adaptive_verification["second_response"] = str(second_response or "")
                    second_evidence_path = self._evidence_path_audit(
                        second_response, self._serialized_evidence_refs(verification_json),
                    )
                    adaptive_verification["second_evidence_path"] = second_evidence_path
                    adaptive_verification["second_diagnostic"] = second_diagnostic or None
                    if answer:
                        answer_evidence_path = second_evidence_path
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
        retrieval_trace["focus_evidence_augmentation"] = focus_evidence_augmentation
        answer_evidence_verified = bool(
            answer_evidence_path
            and answer_evidence_path.get("selected_refs")
            and not answer_evidence_path.get("invalid_refs")
        )
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
            "answer_time_evidence": answer_evidence_audit,
            "verification_evidence": verification_evidence,
            "suggested_paths": suggested_paths,
            "ordering_hint": ordering_hint,
            "ambiguity": ambiguity,
            "ambiguity_policy": self.config.ambiguity_policy,
            "abstained_for_ambiguity": abstained,
            "adaptive_verification": adaptive_verification,
            "answer_evidence_path": answer_evidence_path,
            "answer_evidence_verified": answer_evidence_verified,
            "collision_evidence_expansion": collision_expansion,
            "focus_evidence_augmentation": focus_evidence_augmentation,
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
