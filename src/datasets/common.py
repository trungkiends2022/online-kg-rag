"""Shared JSON and table-normalization helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


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
    header = [str(value).strip() or f"column_{idx}" for idx, value in enumerate(matrix[0])]
    rows = []
    for raw_row in matrix[1:]:
        rows.append({name: raw_row[idx] if idx < len(raw_row) else "" for idx, name in enumerate(header)})
    return rows
