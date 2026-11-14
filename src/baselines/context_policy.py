"""Shared evidence-selection policy for fair context-grounded baselines."""

from __future__ import annotations

from src.datasets.schema import DatasetExample


def all_instance_evidence_retrieval_args(example: DatasetExample) -> dict:
    """Return retrieval settings that preserve every source in one instance.

    The answer-time prompt may still obey its explicit character budget, but
    no baseline may silently discard evidence through a retrieval top-k or a
    row top-k before that budget is applied.
    """
    return {
        "top_k": max(len(example.text_passages), len(example.web_snippets), 1),
        "second_stage_k": 0,
        "max_table_rows": None,
    }
