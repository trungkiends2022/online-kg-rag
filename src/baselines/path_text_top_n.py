"""Path-text ablation that exposes only the planner's top-N path evidence."""

from __future__ import annotations

import json

from src.baselines.online_kg_path_text import OnlineKGPathTextBaseline


class PathTextTopNBaseline(OnlineKGPathTextBaseline):
    """Answer from the planner's top-N paths and their direct evidence.

    ``strict_path_only`` removes table witnesses/constraints from the reader
    payload.  This is the destructive-pruning comparator used in controlled
    experiments; the historical default retains those retrieval artifacts for
    backwards-compatible diagnostic runs.
    """

    method_name = "path_text_top_n"

    def __init__(self, *args, strict_path_only: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.strict_path_only = strict_path_only

    def _bounded_kg_context(
        self, question: str, path_records: list[dict], kg, retrieval_trace: dict,
    ) -> str:
        question_terms = self._terms(question)
        payload = {
            "reasoning_paths": [
                self._path_view(path, rank)
                for rank, path in enumerate(path_records, start=1)
            ],
            "kg_edges": [],
            "text_contexts": [],
        }
        if not self.strict_path_only:
            payload = {
                "table_constraints": retrieval_trace.get("table_constraints", []),
                "table_witnesses": retrieval_trace.get("table_witnesses", []),
                **payload,
            }
        selected_edge_ids: set[str] = set()
        for path in path_records:
            for edge in path.get("edges", []):
                edge_id = str(edge.get("edge_id", ""))
                if not edge_id or edge_id in selected_edge_ids:
                    continue
                edge_view = self._edge_view(edge)
                candidate = {**payload, "kg_edges": [*payload["kg_edges"], edge_view]}
                if len(json.dumps(candidate, ensure_ascii=False)) <= self.config.max_context_chars:
                    payload["kg_edges"].append(edge_view)
                    selected_edge_ids.add(edge_id)

        path_source_ids = {
            str(edge.get("source_id"))
            for path in path_records
            for edge in path.get("edges", [])
            if edge.get("source_id") is not None
        }
        for source_id, context in sorted(kg.text_contexts.items(), key=lambda item: str(item[0])):
            if str(source_id) not in path_source_ids:
                continue
            rendered = " ".join(
                str(context.get(field, "")) for field in ("context_before", "text")
            ).strip()
            compact_context = {
                key: value
                for key, value in dict(context).items()
                if key not in {"text", "context_before"}
            } | {"text": self._clip_text(rendered, question_terms)}
            candidate = {
                **payload,
                "text_contexts": [*payload["text_contexts"], compact_context],
            }
            if len(json.dumps(candidate, ensure_ascii=False)) <= self.config.max_context_chars:
                payload["text_contexts"].append(compact_context)
        return json.dumps(payload, ensure_ascii=False)

    def run(self, example):
        result = super().run(example)
        result["path_context_policy"] = (
            "strict_planner_top_n_paths_only"
            if self.strict_path_only else "planner_top_n_paths_with_retrieval_witnesses"
        )
        result["top_n_paths"] = self.n_paths
        result["strict_path_only"] = self.strict_path_only
        return result
