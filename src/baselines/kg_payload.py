"""Compact, auditable serialization helpers for KG answer prompts."""

from __future__ import annotations


def deduplicate_edge_contexts(edges: list[dict]) -> dict:
    """Keep every edge while storing each passage context once by source id."""
    contexts_by_source_id: dict[str, dict] = {}
    compact_edges: list[dict] = []
    for edge in edges:
        compact_edge = {key: value for key, value in edge.items() if key != "contexts"}
        context_ids: list[str] = []
        for context in edge.get("contexts", []):
            source_id = str(context.get("source_id", "")).strip()
            if not source_id:
                continue
            contexts_by_source_id.setdefault(source_id, dict(context))
            if source_id not in context_ids:
                context_ids.append(source_id)
        compact_edge["context_ids"] = context_ids
        compact_edges.append(compact_edge)
    return {
        "edges": compact_edges,
        "contexts_by_source_id": contexts_by_source_id,
    }
