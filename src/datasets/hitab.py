"""Adapter for HiTab hierarchical-table question answering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from src.datasets.schema import DatasetExample


def _fill_merged_cells(table: dict[str, Any]) -> list[list[str]]:
    texts = [[str(cell).strip() for cell in row] for row in table.get("texts", [])]
    for region in table.get("merged_regions", []):
        r0, r1 = int(region["first_row"]), int(region["last_row"])
        c0, c1 = int(region["first_column"]), int(region["last_column"])
        anchor = texts[r0][c0]
        for row in range(r0, r1 + 1):
            for column in range(c0, c1 + 1):
                if row < len(texts) and column < len(texts[row]):
                    texts[row][column] = anchor
    return texts


def hierarchical_table_to_rows(table: dict[str, Any]) -> list[dict[str, str]]:
    """Materialize each cell with its complete row and column header paths."""
    texts = _fill_merged_cells(table)
    if not texts:
        return []
    top_rows = int(table.get("top_header_rows_num", 1))
    left_columns = int(table.get("left_header_columns_num", 1))
    width = max(map(len, texts))

    # Unlike visual merged cells, HiTab's left_root captures true nested row
    # groups. Repeated leaf labels such as 2012 must remain distinct under
    # "current dollars" and "constant dollars" ancestors.
    hierarchical_row_paths: dict[int, list[str]] = {}

    def visit_left(node: dict[str, Any], ancestors: list[str]) -> None:
        row, column = int(node.get("row_index", -1)), int(node.get("column_index", -1))
        labels = list(ancestors)
        if row >= 0 and column >= 0 and row < len(texts) and column < len(texts[row]):
            label = texts[row][column]
            if label and (not labels or labels[-1] != label):
                labels.append(label)
            hierarchical_row_paths[row] = labels
        for child in node.get("children", []):
            visit_left(child, labels)

    visit_left(table.get("left_root", {}), [])
    column_paths = []
    for column in range(left_columns, width):
        labels = []
        for row in range(min(top_rows, len(texts))):
            value = texts[row][column] if column < len(texts[row]) else ""
            if value and (not labels or labels[-1] != value):
                labels.append(value)
        column_paths.append("__".join(labels) or f"column_{column}")

    rows = []
    for row_index in range(top_rows, len(texts)):
        raw = texts[row_index]
        row_labels = []
        for column in range(min(left_columns, len(raw))):
            value = raw[column]
            if value and (not row_labels or row_labels[-1] != value):
                row_labels.append(value)
        hierarchy = hierarchical_row_paths.get(row_index, [])
        row_path = " / ".join(hierarchy or row_labels) or f"row_{row_index}"
        record = {"row_path": row_path}
        for offset, relation in enumerate(column_paths, start=left_columns):
            if offset < len(raw) and raw[offset] != "":
                # Unique suffixes prevent duplicate hierarchical headers from
                # silently overwriting one another in a Python mapping.
                key, duplicate = relation, 2
                while key in record:
                    key = f"{relation}__{duplicate}"
                    duplicate += 1
                record[key] = raw[offset]
        if len(record) > 1:
            rows.append(record)
    return rows


def load_hitab(
    path: str | Path,
    *,
    tables_dir: str | Path,
    limit: int | None = None,
) -> Iterator[DatasetExample]:
    """Yield HiTab examples without exposing answer-bearing sub-sentences."""
    tables_dir = Path(tables_dir)
    with Path(path).open(encoding="utf-8") as stream:
        for index, line in enumerate(stream):
            if limit is not None and index >= limit:
                break
            if not line.strip():
                continue
            item = json.loads(line)
            table_path = tables_dir / f"{item['table_id']}.json"
            table = json.loads(table_path.read_text(encoding="utf-8"))
            answer = item.get("answer")
            if isinstance(answer, list) and len(answer) == 1:
                answer = answer[0]
            yield DatasetExample(
                example_id=str(item["id"]),
                question=str(item["question"]),
                table_rows=[{
                    "table_name": str(item["table_id"]),
                    "rows": hierarchical_table_to_rows(table),
                    # Every cell already has an exact row/column path. LLM table
                    # enrichment can collapse repeated hierarchy labels or add
                    # unsupported edges, so HiTab uses deterministic triples.
                    "deterministic_only": True,
                }],
                # sub_sentence verbalizes the answer and must not enter retrieval.
                text_passages=[],
                answer=answer,
                metadata={
                    "dataset": "hitab",
                    "table_id": item["table_id"],
                    "table_title": table.get("title", ""),
                    "aggregation": item.get("aggregation", []),
                    "answer_formulas": item.get("answer_formulas", []),
                    "reference_cells_map": item.get("reference_cells_map", {}),
                    "linked_cells": item.get("linked_cells", {}),
                },
            )
