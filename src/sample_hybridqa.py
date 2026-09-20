"""Create a reproducible HybridQA subset with both table and linked-text context."""

from __future__ import annotations

import argparse
import json
import random
import re
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


def answer_source(item: dict[str, Any]) -> str:
    """Summarize the weak traced-answer locations supplied by HybridQA."""
    sources = {
        str(node[-1])
        for node in item.get("answer-node", [])
        if isinstance(node, (list, tuple)) and node
    }
    if sources == {"passage"}:
        return "passage"
    if sources == {"table"}:
        return "table"
    if sources == {"passage", "table"}:
        return "mixed"
    return "unknown"


def _normalized_words(value: Any) -> str:
    return " ".join(re.findall(r"\w+", str(value).casefold()))


def cross_modal_proxy(item: dict[str, Any]) -> str:
    """Estimate whether table lookup is needed before reading a passage.

    For a passage answer-node, HybridQA stores the linked table-cell entity in
    node[0]. If none of those bridge entities occurs in the question, the table
    is likely needed to select the passage. The dataset documents answer-node as
    approximate, so this remains a stratification proxy rather than a gold label.
    """
    question = _normalized_words(item.get("question", ""))
    bridge_entities = [
        _normalized_words(node[0])
        for node in item.get("answer-node", [])
        if (
            isinstance(node, (list, tuple))
            and len(node) >= 4
            and node[-1] == "passage"
            and _normalized_words(node[0])
        )
    ]
    if not bridge_entities:
        return "table_answer"
    if all(entity not in question for entity in bridge_entities):
        return "table_to_text_likely"
    return "bridge_mentioned"


def reasoning_cues(item: dict[str, Any]) -> str:
    question = str(item.get("question", "")).casefold()
    cues = []
    if re.search(
        r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th))\b",
        question,
    ):
        cues.append("ordinal")
    if re.search(
        r"\b(most|least|largest|smallest|highest|lowest|oldest|youngest|earliest|latest|greatest|longest|shortest)\b",
        question,
    ):
        cues.append("superlative")
    if re.search(
        r"\b(between|difference|more than|less than|greater than|compared|how many times|total|sum)\b",
        question,
    ):
        cues.append("comparison_or_count")
    return "+".join(cues) if cues else "other"


def reasoning_attributes(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        answer_kind(item),
        answer_source(item),
        cross_modal_proxy(item),
        reasoning_cues(item),
    )


def _distribution(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    names = ("answer_kind", "answer_source", "cross_modal_proxy", "reasoning_cues")
    counters = [Counter() for _ in names]
    for item in records:
        for counter, value in zip(counters, reasoning_attributes(item)):
            counter[value] += 1
    return {
        name: dict(sorted(counter.items()))
        for name, counter in zip(names, counters)
    }


def select_table_text_records(
    records: list[dict[str, Any]], *, tables_dir: Path, passages_dir: Path,
    require_answer_node: bool = False,
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
        if require_answer_node and not item.get("answer-node"):
            continue
        selected.append(item)
    return selected


def split_sample(
    sample: list[dict[str, Any]], *, shard_size: int,
) -> list[list[dict[str, Any]]]:
    """Split one deterministic sample into non-overlapping fixed-size shards."""
    if shard_size < 1:
        raise ValueError("shard_size must be positive")
    return [sample[start:start + shard_size] for start in range(0, len(sample), shard_size)]


def stratified_shards(
    sample: list[dict[str, Any]], *, shard_size: int, seed: int,
) -> list[list[dict[str, Any]]]:
    """Distribute every reasoning stratum proportionally across fixed-size shards."""
    if shard_size < 1:
        raise ValueError("shard_size must be positive")
    if not sample:
        return []
    capacities = [shard_size] * (len(sample) // shard_size)
    if len(sample) % shard_size:
        capacities.append(len(sample) % shard_size)
    shards: list[list[dict[str, Any]]] = [[] for _ in capacities]
    counts = [Counter() for _ in capacities]
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in sample:
        groups.setdefault(reasoning_attributes(item), []).append(item)

    rng = random.Random(seed)
    # Rare combined strata go first so a full shard cannot exclude them merely
    # because a common stratum consumed its capacity earlier.
    ordered_groups = sorted(groups.items(), key=lambda pair: (len(pair[1]), pair[0]))
    total = len(sample)
    for stratum, items in ordered_groups:
        rng.shuffle(items)
        group_size = len(items)
        for item in items:
            candidates = [
                index for index, shard in enumerate(shards)
                if len(shard) < capacities[index]
            ]
            rng.shuffle(candidates)

            def score(index: int) -> tuple[float, float]:
                target = group_size * capacities[index] / total
                relative_deficit = (target - counts[index][stratum]) / max(target, 1.0)
                capacity_deficit = (capacities[index] - len(shards[index])) / capacities[index]
                return relative_deficit, capacity_deficit

            index = max(candidates, key=score)
            shards[index].append(item)
            counts[index][stratum] += 1

    for shard in shards:
        rng.shuffle(shard)
    return shards


def balanced_sample(
    records: list[dict[str, Any]], *, size: int, seed: int,
    stratify_reasoning: bool = False,
) -> list[dict[str, Any]]:
    if not 0 < size <= len(records):
        raise ValueError(f"size must be between 1 and {len(records)}")
    rng = random.Random(seed)
    remaining = list(records)
    rng.shuffle(remaining)
    dimension_names = (
        ("answer_kind", "answer_source", "cross_modal_proxy", "reasoning_cues")
        if stratify_reasoning else ("answer_kind",)
    )
    attributes = {
        id(item): reasoning_attributes(item) if stratify_reasoning else (answer_kind(item),)
        for item in records
    }
    full = [Counter(values[index] for values in attributes.values()) for index in range(len(dimension_names))]
    chosen: list[dict[str, Any]] = []
    chosen_counts = [Counter() for _ in dimension_names]
    chosen_tables: set[str] = set()
    while len(chosen) < size:
        def score(item: dict[str, Any]) -> float:
            result = 0.0
            for index, value in enumerate(attributes[id(item)]):
                target = size * full[index][value] / len(records)
                deficit = target - chosen_counts[index][value]
                result += deficit / max(target, 1.0)
            return result
        eligible_indices = [
            index for index, item in enumerate(remaining)
            if str(item["table_id"]) not in chosen_tables
        ]
        if not eligible_indices:
            raise ValueError("not enough distinct tables for the requested sample size")
        index = max(eligible_indices, key=lambda i: score(remaining[i]))
        item = remaining.pop(index)
        chosen.append(item)
        for counter, value in zip(chosen_counts, attributes[id(item)]):
            counter[value] += 1
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
    parser.add_argument(
        "--shard-size", type=int,
        help="also write non-overlapping shard files of at most this many examples",
    )
    parser.add_argument(
        "--require-answer-node", action="store_true",
        help="keep only traced examples usable by the HybridQA oracle-evidence baseline",
    )
    parser.add_argument(
        "--stratify-reasoning", action="store_true",
        help="balance answer kind/source, table-to-text proxy, and reasoning cues",
    )
    args = parser.parse_args()
    records = json.loads(args.input.read_text(encoding="utf-8"))
    eligible = select_table_text_records(
        records,
        tables_dir=args.tables_dir,
        passages_dir=args.passages_dir,
        require_answer_node=args.require_answer_node,
    )
    sample = balanced_sample(
        eligible,
        size=args.size,
        seed=args.seed,
        stratify_reasoning=args.stratify_reasoning,
    )
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
            "has_answer_node": args.require_answer_node,
            "stratify_reasoning": args.stratify_reasoning,
        },
        "eligible_distribution": _distribution(eligible),
        "sample_distribution": _distribution(sample),
        "example_ids": [str(item["question_id"]) for item in sample],
        "table_ids": [str(item["table_id"]) for item in sample],
    }
    report_path = args.report or args.output.with_suffix(".distribution.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shard_reports = []
    if args.shard_size is not None:
        shards = stratified_shards(sample, shard_size=args.shard_size, seed=args.seed)
        for index, shard in enumerate(shards, start=1):
            suffix = f"-shard{index:02d}"
            output = args.output.with_name(
                f"{args.output.stem}{suffix}{args.output.suffix}"
            )
            output.write_text(
                json.dumps(shard, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            shard_report = {
                **report,
                "output": str(output),
                "shard_index": index,
                "num_shards": len(shards),
                "sample_size": len(shard),
                "requested_shard_size": args.shard_size,
                "sample_distribution": _distribution(shard),
                "example_ids": [str(item["question_id"]) for item in shard],
                "table_ids": [str(item["table_id"]) for item in shard],
            }
            shard_report_path = output.with_suffix(".distribution.json")
            shard_report_path.write_text(
                json.dumps(shard_report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            shard_reports.append(shard_report)
    print(json.dumps({"sample": report, "shards": shard_reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
