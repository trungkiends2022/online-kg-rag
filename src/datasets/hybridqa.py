"""Adapter for HybridQA with embedded or separately stored WikiTables."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from src.datasets.common import iter_records, read_json
from src.datasets.schema import DatasetExample


def _cell_value(cell: Any) -> str:
    if isinstance(cell, dict):
        return str(cell.get("value", cell.get("text", "")))
    if isinstance(cell, (list, tuple)):
        return str(cell[0]) if cell else ""
    return str(cell)


def _cell_links(cell: Any) -> list[dict]:
    if isinstance(cell, dict):
        links = cell.get("urls", cell.get("links", []))
    elif isinstance(cell, (list, tuple)) and len(cell) > 1:
        links = cell[1]
    else:
        return []
    if isinstance(links, dict):
        links = [links]
    return links if isinstance(links, list) else []


def _link_passage(link: Any, fallback_id: str) -> dict | None:
    if isinstance(link, dict):
        text = link.get("summary") or link.get("text") or link.get("passage")
        source_id = link.get("url") or link.get("id") or fallback_id
    elif isinstance(link, (list, tuple)) and len(link) >= 2:
        source_id, text = link[0], link[1]
    else:
        return None
    if not text:
        return None
    return {"id": str(source_id), "text": str(text)}


def _normalize_table(table: dict, table_id: str) -> tuple[list[dict], list[dict]]:
    raw_header = table.get("header", [])
    header = [_cell_value(cell).strip() or f"column_{idx}" for idx, cell in enumerate(raw_header)]
    rows, passages, seen_passages = [], [], set()
    for row_index, raw_row in enumerate(table.get("data", [])):
        rows.append({
            name: _cell_value(raw_row[col]) if col < len(raw_row) else ""
            for col, name in enumerate(header)
        })
        for col, cell in enumerate(raw_row):
            for link_index, link in enumerate(_cell_links(cell)):
                passage = _link_passage(link, f"{table_id}:{row_index}:{col}:{link_index}")
                if passage and passage["id"] not in seen_passages:
                    seen_passages.add(passage["id"])
                    passages.append(passage)

    # Some processed variants put passages at table level instead of in cells.
    for key in ("passages", "text_passages"):
        for idx, passage in enumerate(table.get(key, [])):
            normalized = _link_passage(passage, f"{table_id}:passage:{idx}")
            if normalized and normalized["id"] not in seen_passages:
                seen_passages.add(normalized["id"])
                passages.append(normalized)
    return rows, passages


def _load_external_table(tables_dir: Path, table_id: str) -> dict:
    candidates = [tables_dir / f"{table_id}.json", tables_dir / table_id]
    for candidate in candidates:
        if candidate.is_file():
            return read_json(candidate)
    raise FileNotFoundError(
        f"Cannot find table {table_id!r} under {tables_dir}. "
        "Pass the WikiTables-WithLinks tables directory or use an embedded-table export."
    )


def _as_passage_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "summary", "passage"):
            if key in value:
                return _as_passage_text(value[key])
        return ""
    if isinstance(value, list):
        return " ".join(filter(None, (_as_passage_text(part) for part in value)))
    return str(value)


def _load_external_passages(passages_dir: Path, table_id: str) -> list[dict]:
    path = passages_dir / f"{table_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Cannot find passages for table {table_id!r} at {path}")
    payload = read_json(path)
    passages = []
    if isinstance(payload, dict):
        source_items = payload.items()
    elif isinstance(payload, list):
        source_items = enumerate(payload)
    else:
        raise ValueError(f"Unsupported HybridQA passage payload in {path}")
    for passage_id, value in source_items:
        text = _as_passage_text(value)
        if text:
            passages.append({"id": str(passage_id), "text": text})
    return passages


def load_hybridqa(
    path: str | Path,
    tables_dir: str | Path | None = None,
    passages_dir: str | Path | None = None,
    limit: int | None = None,
) -> Iterator[DatasetExample]:
    """Yield HybridQA records in oracle-context mode.

    Supported inputs are an export containing an embedded ``table`` object, or
    the official question file plus a directory containing ``<table_id>.json``.
    Linked passage summaries are extracted from table cells when present.
    """
    table_root = Path(tables_dir) if tables_dir else None
    passage_root = Path(passages_dir) if passages_dir else None
    for index, item in enumerate(iter_records(read_json(path))):
        if limit is not None and index >= limit:
            break
        table_id = str(item.get("table_id") or item.get("table", {}).get("uid") or index)
        table = item.get("table")
        if not isinstance(table, dict):
            if table_root is None:
                raise ValueError(
                    "HybridQA record has no embedded table; --tables-dir is required"
                )
            table = _load_external_table(table_root, table_id)
        rows, passages = _normalize_table(table, table_id)
        if passage_root is not None:
            external = _load_external_passages(passage_root, table_id)
            known_ids = {passage["id"] for passage in passages}
            passages.extend(passage for passage in external if passage["id"] not in known_ids)
        example_id = str(item.get("question_id") or item.get("id") or index)
        yield DatasetExample(
            example_id=example_id,
            question=str(item["question"]),
            table_rows=[{"table_name": table.get("title") or table_id, "rows": rows}],
            text_passages=passages,
            answer=item.get("answer_text", item.get("answer-text", item.get("answer"))),
            metadata={"dataset": "hybridqa", "table_id": table_id},
        )
