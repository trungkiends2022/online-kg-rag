"""Adapter for the official FinQA JSON files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from src.datasets.common import iter_records, matrix_to_rows, read_json
from src.datasets.schema import DatasetExample


def load_finqa(
    path: str | Path,
    limit: int | None = None,
    table_format: str = "official",
) -> Iterator[DatasetExample]:
    """Yield FinQA documents as pipeline examples.

    The official file contains one document and one QA object per record.  Text is
    deliberately kept as separate passages so the existing retriever can rank it.
    Gold programs and supporting-fact annotations are retained in ``metadata``.
    """
    for index, item in enumerate(iter_records(read_json(path))):
        if limit is not None and index >= limit:
            break
        qa = item.get("qa", {})
        example_id = str(item.get("id") or item.get("filename") or index)
        if table_format not in {"official", "raw"}:
            raise ValueError("table_format must be 'official' or 'raw'")
        matrix = (
            item.get("table") or item.get("table_ori") or []
            if table_format == "official"
            else item.get("table_ori") or item.get("table") or []
        )
        passages = []
        for position, text in enumerate(item.get("pre_text", [])):
            passages.append({"id": f"{example_id}:pre:{position}", "text": str(text)})
        for position, text in enumerate(item.get("post_text", [])):
            passages.append({"id": f"{example_id}:post:{position}", "text": str(text)})

        yield DatasetExample(
            example_id=example_id,
            question=str(qa["question"]),
            table_rows=[{"table_name": example_id, "rows": matrix_to_rows(matrix)}],
            text_passages=passages,
            answer=qa.get("exe_ans", qa.get("answer")),
            metadata={
                "dataset": "finqa",
                "display_answer": qa.get("answer"),
                "program": qa.get("program"),
                "program_re": qa.get("program_re"),
                "gold_evidence": qa.get("gold_inds", {}),
                "table_format": table_format,
            },
        )
