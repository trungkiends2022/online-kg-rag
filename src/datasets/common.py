"""Shared JSON and table-normalization helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _unique_headers(values: list[str]) -> list[str]:
    """Return positional, non-empty headers without silently overwriting cells."""
    counts: dict[str, int] = {}
    headers = []
    for index, value in enumerate(values):
        base = value or f"column_{index}"
        counts[base] = counts.get(base, 0) + 1
        headers.append(base if counts[base] == 1 else f"{base}__{counts[base]}")
    return headers


def read_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_records(payload: Any) -> Iterable[dict]:
    """Accept a JSON array or common ``{"data": [...]}`` wrappers."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "examples", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("Expected a JSON list or an object containing data/examples/records")


def matrix_to_rows(matrix: list[list[Any]]) -> list[dict[str, Any]]:
    if not matrix:
        return []
    first = [str(value).strip() for value in matrix[0]]
    data_start = 1
    # FinQA frequently uses a two-level header, e.g. years on the first row and
    # High/Low/Dividend on the second. Expand it without dropping trailing cells.
    if len(matrix) > 2 and len(matrix[1]) > len(first) and len(first) > 1:
        second = [str(value).strip() for value in matrix[1]]
        value_columns = len(second) - 1
        groups = len(first) - 1
        if value_columns > 0 and value_columns % groups == 0:
            span = value_columns // groups
            header = [second[0] or "row"]
            for index in range(1, len(second)):
                group = first[1 + (index - 1) // span]
                field = second[index] or f"value_{index}"
                header.append(f"{group}_{field}" if group else field)
            data_start = 2
        else:
            header = _unique_headers(first)
    else:
        # Some raw FinQA tables repeat a year-group inline, e.g.
        # [2002, High, Low, 2001, High, Low]. Qualify the following fields.
        if any(value.isdigit() and len(value) == 4 for value in first):
            expanded, group = [], ""
            for index, value in enumerate(first):
                if value.isdigit() and len(value) == 4:
                    group = value
                    expanded.append(value if index == 0 else f"{value}_period")
                else:
                    expanded.append(f"{group}_{value}" if group and value else value)
            header = _unique_headers(expanded)
        else:
            header = _unique_headers(first)
    widest = max((len(row) for row in matrix[data_start:]), default=len(header))
    if widest > len(header):
        header.extend(f"column_{index}" for index in range(len(header), widest))
    rows = []
    for raw_row in matrix[data_start:]:
        rows.append({name: raw_row[idx] if idx < len(raw_row) else "" for idx, name in enumerate(header)})
    return rows
