"""Lossless-first compact serialization for OUEG answer prompts.

The audit payload remains a normal, fully expanded JSON object.  This module
creates the separate representation sent to the answer model: it removes only
redundant syntax by default and keeps every KG edge addressable by a short ID.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

_EMPTY = (None, "", [], {}, ())
_ROW_ID = re.compile(r"^table:(?P<table>.+):row:(?P<index>\d+)$")
_COLUMN_ID = re.compile(r"^table:(?P<table>.+):column:(?P<column>.+)$")
_CELL_ID = re.compile(r"^table:(?P<table>.+):row:(?P<index>\d+):cell:(?P<column>.+)$")


@dataclass(frozen=True)
class OUEGPromptCompressionConfig:
    """Serialization policy; ``lossless`` is the safe default."""

    context_mode: str = "lossless"
    snippet_min_chars: int = 900
    snippet_max_sentences: int = 4
    score_precision: int = 1
    include_lexical_tiebreak: bool = True

    def validate(self) -> None:
        if self.context_mode not in {"lossless", "extractive"}:
            raise ValueError("context_mode must be lossless or extractive")
        if self.snippet_min_chars < 1 or self.snippet_max_sentences < 1:
            raise ValueError("snippet limits must be positive")
        if self.score_precision < 0:
            raise ValueError("score_precision must be non-negative")
        if not isinstance(self.include_lexical_tiebreak, bool):
            raise ValueError("include_lexical_tiebreak must be boolean")


class CompactOUEGPromptBuilder:
    """Serialize a full OUEG subgraph without candidate or edge filtering."""

    def __init__(self, config: OUEGPromptCompressionConfig | None = None):
        self.config = config or OUEGPromptCompressionConfig()
        self.config.validate()

    @staticmethod
    def _terms(value: object) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", str(value).casefold()))

    @staticmethod
    def _remove_empty(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: CompactOUEGPromptBuilder._remove_empty(item)
                for key, item in value.items()
                if item not in _EMPTY
            }
        if isinstance(value, list):
            return [CompactOUEGPromptBuilder._remove_empty(item) for item in value if item not in _EMPTY]
        return value

    @staticmethod
    def _header_label(edge: dict) -> str:
        header_path = edge.get("header_path")
        if isinstance(header_path, (list, tuple)) and len(header_path) > 1:
            return " > ".join(str(part) for part in header_path)
        return str(edge.get("column_name") or edge.get("relation") or "value")

    @staticmethod
    def _table_and_row(node: object) -> tuple[str, int] | None:
        match = _ROW_ID.match(str(node))
        if not match:
            return None
        return match.group("table"), int(match.group("index"))

    def _context_text(self, question: str, text: str, entity_terms: set[str]) -> tuple[str, bool]:
        """Return lossless text unless extractive mode is explicitly enabled."""
        if self.config.context_mode != "extractive" or len(text) <= self.config.snippet_min_chars:
            return text, False
        question_terms = self._terms(question) | entity_terms
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
        if len(sentences) <= self.config.snippet_max_sentences:
            return text, False
        ranked = sorted(
            range(len(sentences)),
            key=lambda index: (
                -len(self._terms(sentences[index]) & question_terms), index,
            ),
        )
        selected = set()
        for index in ranked[:2]:
            selected.update(range(max(0, index - 1), min(len(sentences), index + 2)))
        return " ".join(sentences[index] for index in sorted(selected)), True

    @staticmethod
    def _range_encode(ids: list[str]) -> str:
        """Keep edge IDs readable; collapse only consecutive eN sequences."""
        output, index = [], 0
        while index < len(ids):
            match = re.fullmatch(r"e(\d+)", ids[index])
            if not match:
                output.append(ids[index])
                index += 1
                continue
            start = end = int(match.group(1))
            cursor = index + 1
            while cursor < len(ids):
                next_match = re.fullmatch(r"e(\d+)", ids[cursor])
                if not next_match or int(next_match.group(1)) != end + 1:
                    break
                end += 1
                cursor += 1
            output.append(f"e{start}" if start == end else f"e{start}-e{end}")
            index = cursor
        return ",".join(output)

    def _compact_ambiguity(self, ambiguity: dict) -> dict:
        groups = []
        for group in ambiguity.get("groups", []):
            groups.append(self._remove_empty({
                "bridge": group.get("bridge_entity"),
                "n": group.get("candidate_count"),
                "status": group.get("status"),
                "candidates": [self._remove_empty({
                    "id": candidate.get("path_id"),
                    "entity": candidate.get("entity"),
                    "row": candidate.get("row_order_index"),
                    "score": round(float(candidate.get("score", 0.0)), self.config.score_precision),
                    "lex": round(float(candidate.get("lexical_overlap_with_bridge_entity", 0.0)), self.config.score_precision) if self.config.include_lexical_tiebreak else None,
                }) for candidate in group.get("candidates", [])],
                "lexical_tiebreak": self._remove_empty({
                    "winner": group.get("lexical_tiebreak", {}).get("winner"),
                    "eligible": group.get("lexical_tiebreak", {}).get("eligible"),
                }) if self.config.include_lexical_tiebreak else None,
            }))
        return self._remove_empty({
            "is_ambiguous": ambiguity.get("is_ambiguous"),
            "status": ambiguity.get("status"),
            "groups": groups,
            "lexical_tiebreak_winner": ambiguity.get("selective_prediction", {}).get("lexical_tiebreak_winner") if self.config.include_lexical_tiebreak else None,
        })

    def build(
        self,
        *,
        question: str,
        records: list[dict],
        contexts_by_source_id: dict[str, dict],
        suggested_paths: list[dict],
        ordering_hint: dict,
        ambiguity: dict,
        path_generation: dict,
    ) -> dict:
        """Return compact payload plus metadata proving what was retained."""
        tables: dict[str, str] = {}
        for edge in records:
            parsed = self._table_and_row(edge.get("head")) or self._table_and_row(edge.get("tail"))
            if parsed:
                tables.setdefault(parsed[0], f"t{len(tables)}")
        table_legend = {short: full for full, short in tables.items()}

        source_ids = sorted({str(source_id) for source_id in contexts_by_source_id})
        passage_ids = {source_id: f"p{index}" for index, source_id in enumerate(source_ids)}
        edge_ids = {str(edge.get("edge_id")): f"e{index}" for index, edge in enumerate(records)}

        def node_id(value: object) -> str:
            raw = str(value)
            parsed = self._table_and_row(raw)
            if parsed:
                table, index = parsed
                return f"{tables.get(table, table)}:r{index}"
            match = _COLUMN_ID.match(raw)
            if match:
                return f"{tables.get(match.group('table'), match.group('table'))}:c:{match.group('column')}"
            match = _CELL_ID.match(raw)
            if match:
                return f"{tables.get(match.group('table'), match.group('table'))}:r{match.group('index')}:c:{match.group('column')}"
            if raw.startswith("passage:"):
                source_id = raw.removeprefix("passage:")
                return passage_ids.get(source_id, raw)
            return raw

        by_head: dict[str, list[dict]] = defaultdict(list)
        for edge in records:
            by_head[str(edge.get("head"))].append(edge)

        row_records = []
        represented_edges: set[str] = set()
        row_anchors = [
            edge for edge in records
            if edge.get("relation") == "has_record" and self._table_and_row(edge.get("tail"))
        ]
        seen_rows = set()
        for anchor in sorted(row_anchors, key=lambda edge: (str(edge.get("tail")), str(edge.get("head")))):
            row_id = str(anchor["tail"])
            if row_id in seen_rows:
                continue
            seen_rows.add(row_id)
            parsed = self._table_and_row(row_id)
            assert parsed is not None
            table_name, row_index = parsed
            values: dict[str, list[str]] = defaultdict(list)
            row_edge_ids = [edge_ids[str(anchor.get("edge_id"))]]
            represented_edges.add(str(anchor.get("edge_id")))
            for edge in by_head[row_id]:
                tail = str(edge.get("tail", ""))
                if (
                    not edge.get("structural")
                    or edge.get("relation") == "has_record"
                    or edge.get("cell_node")
                    or ":cell:" in tail
                ):
                    continue
                column = self._header_label(edge)
                values[column].append(node_id(tail))
                edge_key = str(edge.get("edge_id"))
                row_edge_ids.append(edge_ids[edge_key])
                represented_edges.add(edge_key)
            # Explicitly preserve row-level hyperlink bridges in the row bundle.
            for edge in records:
                if (
                    edge.get("relation") == "linked_passage"
                    and edge.get("row_index") == row_index
                    and str(edge.get("source_id")) == table_name
                ):
                    values.setdefault("passage", []).append(node_id(edge.get("tail")))
                    edge_key = str(edge.get("edge_id"))
                    row_edge_ids.append(edge_ids[edge_key])
                    represented_edges.add(edge_key)
            row_records.append({
                "table": tables.get(table_name, table_name),
                "row": f"r{row_index}",
                "order": row_index,
                "entity": node_id(anchor.get("head")),
                "values": {key: " | ".join(dict.fromkeys(value)) for key, value in sorted(values.items())},
                "edges": self._range_encode(list(dict.fromkeys(row_edge_ids))),
            })

        # All edges not conveyed by a compact row record remain as one schema
        # table. This includes every text fact and every topology edge needed
        # for multi-hop traversal.
        edge_rows = []
        for edge in records:
            raw_id = str(edge.get("edge_id"))
            if raw_id in represented_edges:
                continue
            raw_context_ids = edge.get("context_ids") or [
                str(context.get("source_id", ""))
                for context in edge.get("contexts", [])
                if context.get("source_id")
            ]
            context_refs = [
                passage_ids[source_id]
                for source_id in raw_context_ids
                if source_id in passage_ids
            ]
            provenance = {
                "type": edge.get("source_type"),
                "src": tables.get(str(edge.get("source_id")), edge.get("source_id")),
                "row": edge.get("row_index"),
                "col": self._header_label(edge) if edge.get("column_name") or edge.get("header_path") else None,
                "group": edge.get("source_group"),
            }
            edge_rows.append(self._remove_empty({
                "id": edge_ids[raw_id],
                "h": node_id(edge.get("head")),
                "r": edge.get("relation"),
                "t": node_id(edge.get("tail")),
                "p": provenance,
                "ctx": context_refs,
            }))

        entity_terms = {
            term for path in suggested_paths
            for term in self._terms(path.get("anchor_entity", ""))
        }
        compact_contexts = {}
        context_truncated = 0
        for source_id, context in sorted(contexts_by_source_id.items()):
            source_id = str(source_id)
            text, truncated = self._context_text(question, str(context.get("text", "")), entity_terms)
            context_truncated += int(truncated)
            compact_contexts[passage_ids.setdefault(source_id, f"p{len(passage_ids)}")] = self._remove_empty({
                "src": source_id,
                "text": text,
                "before": context.get("context_before"),
                "extractive_snippet": True if truncated else None,
            })

        prompt_paths = []
        for path in suggested_paths:
            prompt_paths.append(self._remove_empty({
                "id": path.get("path_id"),
                "kind": path.get("path_kind"),
                "role": path.get("role"),
                "row": node_id(path["row_id"]) if path.get("row_id") else None,
                "entity": node_id(path.get("anchor_entity")),
                "bridge": node_id(path.get("bridge_entity")),
                "edges": self._range_encode([
                    edge_ids.get(str(edge_id), str(edge_id)) for edge_id in path.get("edge_ids", [])
                ]),
                "score": round(float(path.get("score", 0.0)), self.config.score_precision),
                "lex": round(float(path.get("lexical_overlap_with_bridge_entity", 0.0)), self.config.score_precision) if self.config.include_lexical_tiebreak else None,
            }))

        direct_table_match = any(
            self._terms(question) & self._terms(column)
            for row in row_records for column in row["values"]
        )
        payload = self._remove_empty({
            "format": "oueg-compact-v1",
            "legend": {
                "tables": table_legend,
                "passages": {short: source for source, short in passage_ids.items()},
                "ids": "e=edge; t:r=row; t:c=column; p=passage",
                "edge_schema": ["id", "h", "r", "t", "p(type,src,row,col,group)", "ctx"],
            },
            "rows": row_records,
            "edges": edge_rows,
            "contexts": compact_contexts,
            "paths": prompt_paths,
            "ordering": ordering_hint,
            "ambiguity": self._compact_ambiguity(ambiguity),
            # This is presentation-only: facts remain in ``edges`` regardless.
            "extended_hops": [] if direct_table_match else [
                path["id"] for path in prompt_paths if path.get("kind") == "seed_expansion"
            ],
            "path_generation": path_generation,
        })
        rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
        return {
            "payload": payload,
            "json": rendered,
            "stats": {
                "full_edge_count": len(records),
                "row_record_count": len(row_records),
                "edge_record_count": len(edge_rows),
                "context_count": len(compact_contexts),
                "extractive_context_count": context_truncated,
                "all_edges_represented": len(edge_rows) + len(represented_edges) == len(records),
                "prompt_payload_chars": len(rendered),
            },
        }

    def prompt(self, *, question: str, compact_json: str, tie_break_hint: str = "") -> str:
        return f"""Answer the question using the complete compact OUEG payload.

`rows` retains every table row, its original order, values, passage references, and edge IDs. `edges` uses the legend schema and contains every KG edge not already represented in a row; no candidate or fact has been pruned. `contexts` are deduplicated by passage ID. `paths` are reading guides only. Their `score` is rounded relevance metadata. `lex`, when present, is a weak lexical tie-break rather than factual proof. Follow `ordering` when present; use `edges` and `contexts` for multi-hop evidence. Return only the shortest answer span.{tie_break_hint}

Question: {question}
Compact OUEG payload: {compact_json}
Answer:"""
