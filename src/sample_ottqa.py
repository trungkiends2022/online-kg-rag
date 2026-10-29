"""Create a reproducible, ODYSSEY-style OTT-QA development benchmark."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from src.sample_hybridqa import (
    balanced_sample,
    stratified_shards,
    _distribution as _hybridqa_distribution,
)


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


def load_question_ids(path_or_paths: Path | list[Path]) -> set[str]:
    """Read question IDs from one or more OTT-QA/HybridQA JSON splits."""
    paths = path_or_paths if isinstance(path_or_paths, list) else [path_or_paths]
    all_ids: set[str] = set()
    for path in paths:
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError(f"expected a JSON list in {path}")
        all_ids.update(str(item["question_id"]) for item in records if item.get("question_id"))
    return all_ids


def select_eligible_records(
    records: list[dict[str, Any]], *, tables_dir: Path, passages_dir: Path,
    excluded_question_ids: set[str] | None = None,
    require_answer_node: bool = False,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Keep runnable OTT-QA records and report filtering reasons.

    The local adapter requires the table and linked-text JSON files.
    """
    excluded_question_ids = excluded_question_ids or set()
    eligible: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for item in records:
        question_id = str(item.get("question_id", ""))
        table_id = str(item.get("table_id", ""))
        if not question_id:
            skipped["missing_question_id"] += 1
        elif question_id in excluded_question_ids:
            skipped["overlaps_hybridqa_dev"] += 1
        elif not table_id or not (tables_dir / f"{table_id}.json").is_file():
            skipped["missing_table_file"] += 1
        elif not _has_text_context(passages_dir, table_id):
            skipped["missing_or_empty_linked_text_file"] += 1
        elif not str(item.get("answer-text", "")).strip():
            skipped["missing_gold_answer"] += 1
        elif require_answer_node and not item.get("answer-node"):
            skipped["missing_answer_node"] += 1
        else:
            eligible.append(item)
    return eligible, skipped


def uniform_sample(
    records: list[dict[str, Any]], *, size: int, seed: int,
) -> list[dict[str, Any]]:
    if not 0 < size <= len(records):
        raise ValueError(f"size must be between 1 and {len(records)}")
    return random.Random(seed).sample(records, size)


def split_sample(
    sample: list[dict[str, Any]], *, shard_size: int,
) -> list[list[dict[str, Any]]]:
    if shard_size < 1:
        raise ValueError("shard_size must be positive")
    return [sample[start:start + shard_size] for start in range(0, len(sample), shard_size)]


def _answer_shape(item: dict[str, Any]) -> str:
    answer = item.get("answer-text")
    return "list" if isinstance(answer, list) else "scalar"


def _distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    dist: dict[str, Any] = {
        "answer_shape": dict(sorted(Counter(_answer_shape(item) for item in records).items())),
        "unique_table_count": len({str(item.get("table_id", "")) for item in records}),
    }
    dist.update(_hybridqa_distribution(records))
    return dist


def _report(
    *, input_path: Path, output: Path, seed: int, requested_size: int,
    population_size: int, eligible: list[dict[str, Any]], skipped: Counter[str],
    sample: list[dict[str, Any]], excluded_question_ids_path: Path | None,
    require_answer_node: bool = False,
    stratify_reasoning: bool = False,
) -> dict[str, Any]:
    return {
        "source": str(input_path),
        "output": str(output),
        "seed": seed,
        "sample_size": len(sample),
        "requested_sample_size": requested_size,
        "population_size": population_size,
        "eligible_population_size": len(eligible),
        "excluded_question_ids_source": (
            [str(p) for p in excluded_question_ids_path]
            if isinstance(excluded_question_ids_path, list)
            else (str(excluded_question_ids_path) if excluded_question_ids_path else None)
        ),
        "selection": {
            "method": "balanced_stratified" if stratify_reasoning else "uniform_without_replacement",
            "unique_tables": stratify_reasoning,
            "stratified": stratify_reasoning,
            "has_table_file": True,
            "has_nonempty_linked_text_file": True,
            "has_gold_answer": True,
            "has_answer_node": require_answer_node,
        },
        "skipped": dict(sorted(skipped.items())),
        "eligible_distribution": _distribution(eligible),
        "sample_distribution": _distribution(sample),
        "example_ids": [str(item["question_id"]) for item in sample],
        "table_ids": [str(item["table_id"]) for item in sample],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tables-dir", type=Path, required=True)
    parser.add_argument("--passages-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--exclude-question-ids-from", type=Path, nargs="+",
        help="one or more paths to JSON files containing question IDs to exclude",
    )
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--shard-size", type=int, default=100)
    parser.add_argument(
        "--require-answer-node", action="store_true",
        help="keep only traced examples with answer-node provenance",
    )
    parser.add_argument(
        "--stratify-reasoning", action="store_true",
        help="balance answer kind/source, table-to-text proxy, and reasoning cues, enforcing unique tables",
    )
    args = parser.parse_args()

    records = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"expected a JSON list in {args.input}")
    excluded = (
        load_question_ids(args.exclude_question_ids_from)
        if args.exclude_question_ids_from else set()
    )
    eligible, skipped = select_eligible_records(
        records,
        tables_dir=args.tables_dir,
        passages_dir=args.passages_dir,
        excluded_question_ids=excluded,
        require_answer_node=args.require_answer_node,
    )
    if args.stratify_reasoning:
        sample = balanced_sample(
            eligible,
            size=args.size,
            seed=args.seed,
            stratify_reasoning=True,
        )
    else:
        sample = uniform_sample(eligible, size=args.size, seed=args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = _report(
        input_path=args.input,
        output=args.output,
        seed=args.seed,
        requested_size=args.size,
        population_size=len(records),
        eligible=eligible,
        skipped=skipped,
        sample=sample,
        excluded_question_ids_path=args.exclude_question_ids_from,
        require_answer_node=args.require_answer_node,
        stratify_reasoning=args.stratify_reasoning,
    )
    report_path = args.report or args.output.with_suffix(".distribution.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.stratify_reasoning:
        shards = stratified_shards(sample, shard_size=args.shard_size, seed=args.seed)
    else:
        shards = split_sample(sample, shard_size=args.shard_size)

    shard_reports = []
    for index, shard in enumerate(shards, start=1):
        shard_output = args.output.with_name(
            f"{args.output.stem}-shard{index:02d}{args.output.suffix}"
        )
        shard_output.write_text(
            json.dumps(shard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shard_report = {
            **report,
            "output": str(shard_output),
            "shard_index": index,
            "num_shards": len(shards),
            "sample_size": len(shard),
            "requested_shard_size": args.shard_size,
            "sample_distribution": _distribution(shard),
            "example_ids": [str(item["question_id"]) for item in shard],
            "table_ids": [str(item["table_id"]) for item in shard],
        }
        shard_output.with_suffix(".distribution.json").write_text(
            json.dumps(shard_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shard_reports.append(shard_report)
    print(json.dumps({"sample": report, "shards": shard_reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
