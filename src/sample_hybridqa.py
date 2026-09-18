"""Create a reproducible HybridQA subset with both table and linked-text context."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


def _has_text_context(passages_dir: Path, table_id: str) -> bool:
    path = passages_dir / f"{table_id}.json"
    if not path.is_file():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        values = payload.values()
    elif isinstance(payload, list):
        values = payload
    else:
        return False
    return any(str(value).strip() for value in values)


def answer_kind(item: dict[str, Any]) -> str:
    answer = str(item.get("answer-text", "")).strip()
    compact = answer.replace(",", "").replace(".", "", 1)
    return "numeric" if compact.replace("-", "", 1).isdigit() else "text"


def select_table_text_records(
    records: list[dict[str, Any]], *, tables_dir: Path, passages_dir: Path,
) -> list[dict[str, Any]]:
    """Keep answer-bearing dev examples whose table and linked passages exist."""
    selected = []
    for item in records:
        table_id = str(item.get("table_id", ""))
        if not table_id or not (tables_dir / f"{table_id}.json").is_file():
            continue
        if not _has_text_context(passages_dir, table_id):
            continue
        if not str(item.get("answer-text", "")).strip():
            continue
        selected.append(item)
    return selected


def balanced_sample(records: list[dict[str, Any]], *, size: int, seed: int) -> list[dict[str, Any]]:
    if not 0 < size <= len(records):
        raise ValueError(f"size must be between 1 and {len(records)}")
    rng = random.Random(seed)
    remaining = list(records)
    rng.shuffle(remaining)
    full = Counter(answer_kind(item) for item in records)
    chosen: list[dict[str, Any]] = []
    chosen_counts: Counter[str] = Counter()
    chosen_tables: set[str] = set()
    while len(chosen) < size:
        def score(item: dict[str, Any]) -> float:
            kind = answer_kind(item)
            target = size * full[kind] / len(records)
            return target - chosen_counts[kind]
        eligible_indices = [
            index for index, item in enumerate(remaining)
            if str(item["table_id"]) not in chosen_tables
        ]
        if not eligible_indices:
            raise ValueError("not enough distinct tables for the requested sample size")
        index = max(eligible_indices, key=lambda i: score(remaining[i]))
        item = remaining.pop(index)
        chosen.append(item)
        chosen_counts[answer_kind(item)] += 1
        chosen_tables.add(str(item["table_id"]))
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tables-dir", type=Path, required=True)
    parser.add_argument("--passages-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2027)
    args = parser.parse_args()
    records = json.loads(args.input.read_text(encoding="utf-8"))
    eligible = select_table_text_records(
        records, tables_dir=args.tables_dir, passages_dir=args.passages_dir
    )
    sample = balanced_sample(eligible, size=args.size, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "source": str(args.input),
        "output": str(args.output),
        "seed": args.seed,
        "sample_size": args.size,
        "population_size": len(records),
        "eligible_population_size": len(eligible),
        "selection_criteria": {
            "has_table_file": True,
            "has_nonempty_linked_text_file": True,
            "has_gold_answer": True,
        },
        "sample_answer_kind": dict(sorted(Counter(answer_kind(item) for item in sample).items())),
        "example_ids": [str(item["question_id"]) for item in sample],
        "table_ids": [str(item["table_id"]) for item in sample],
    }
    report_path = args.report or args.output.with_suffix(".distribution.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
