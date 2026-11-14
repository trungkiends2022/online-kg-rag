"""Adapter for OTT-QA's official train/dev table-and-passage resources.

The official OTT-QA question splits contain a ``table_id`` but not an embedded
table.  For train and dev, the checked-out dataset supplies the corresponding
table and its linked passages in separate, per-table JSON files.  Loading that
pair is an oracle-context view: it is useful for validating the reader and KG
components, but it is not a full open-domain OTT-QA retrieval evaluation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from src.datasets.hybridqa import (
    _load_external_passages,
    _load_external_table,
    _normalize_table,
)
from src.datasets.common import iter_records, read_json
from src.datasets.schema import DatasetExample


def load_ottqa(
    path: str | Path,
    *,
    tables_dir: str | Path,
    passages_dir: str | Path | None = None,
    limit: int | None = None,
    example_id: str | None = None,
) -> Iterator[DatasetExample]:
    """Yield OTT-QA examples using their provided train/dev table context.

    ``tables_dir`` is normally ``data/OTT-QA/data/traindev_tables_tok`` and
    ``passages_dir`` is normally ``data/OTT-QA/data/traindev_request_tok``.
    The official test split has no table context in these directories, so it
    cannot be used by this oracle-context adapter.
    """
    table_root = Path(tables_dir)
    passage_root = Path(passages_dir) if passages_dir else None
    for index, item in enumerate(iter_records(read_json(path))):
        if limit is not None and index >= limit:
            break
        item_id = str(item.get("question_id") or item.get("id") or index)
        if example_id is not None and item_id != str(example_id):
            continue
        table_id = str(item.get("table_id") or "")
        if not table_id:
            raise ValueError(f"OTT-QA record {item_id!r} has no table_id")
        table = _load_external_table(table_root, table_id)
        rows, passages, cell_links = _normalize_table(table, table_id)
        if passage_root is not None:
            passages = _load_external_passages(passage_root, table_id)
        yield DatasetExample(
            example_id=item_id,
            question=str(item["question"]),
            table_rows=[{
                "table_name": table.get("title") or table_id,
                "rows": rows,
                "cell_links": cell_links,
            }],
            text_passages=passages,
            answer=item.get("answer-text", item.get("answer_text", item.get("answer"))),
            metadata={
                "dataset": "ottqa",
                "table_id": table_id,
                "answer_nodes": item.get("answer-node", []),
                "evaluation_context": "oracle_train_dev_table_and_passages",
            },
        )
