"""Create a deterministic, distribution-aware FinQA pilot subset."""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any


OPERATOR_RE = re.compile(r"([A-Za-z_]+)\s*\(")


def attributes(item: dict[str, Any]) -> tuple[str, str, str]:
    qa = item.get("qa", {})
    operators = OPERATOR_RE.findall(str(qa.get("program", "")))
    final_operator = operators[-1] if operators else "none"
    step_bucket = "1" if len(operators) <= 1 else "2" if len(operators) == 2 else "3+"
    evidence = qa.get("gold_inds") or {}
    has_table = any(str(key).startswith("table") for key in evidence)
    has_text = any(not str(key).startswith("table") for key in evidence)
    modality = "both" if has_table and has_text else "table_only" if has_table else "text_only" if has_text else "none"
    return final_operator, modality, step_bucket


def _distribution(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    dimensions = [Counter(), Counter(), Counter()]
    for record in records:
        for counter, value in zip(dimensions, attributes(record)):
            counter[value] += 1
    return {
        "final_operator": dict(sorted(dimensions[0].items())),
        "evidence_modality": dict(sorted(dimensions[1].items())),
        "program_steps": dict(sorted(dimensions[2].items())),
    }


def balanced_sample(records: list[dict[str, Any]], size: int, seed: int) -> list[dict[str, Any]]:
    if not 0 < size <= len(records):
        raise ValueError(f"size must be between 1 and {len(records)}")
    rng = random.Random(seed)
    remaining = list(records)
    rng.shuffle(remaining)
    full = _distribution(records)
    selected: list[dict[str, Any]] = []
    selected_counts = [Counter(), Counter(), Counter()]

    # Guarantee coverage of every final operator when the requested size allows.
    operators = sorted(full["final_operator"], key=lambda op: (full["final_operator"][op], op))
    for operator in operators:
        candidate = next((item for item in remaining if attributes(item)[0] == operator), None)
        if candidate is None or len(selected) >= size:
            break
        selected.append(candidate)
        remaining.remove(candidate)
        for counter, value in zip(selected_counts, attributes(candidate)):
            counter[value] += 1

    dimension_names = ("final_operator", "evidence_modality", "program_steps")
    while len(selected) < size:
        # Greedily fill the largest marginal deficits relative to the full dev
        # distribution. Seeded shuffling supplies deterministic tie-breaking.
        def score(item: dict[str, Any]) -> float:
            result = 0.0
            for index, (name, value) in enumerate(zip(dimension_names, attributes(item))):
                target = size * full[name].get(value, 0) / len(records)
                deficit = target - selected_counts[index][value]
                result += deficit / max(target, 1.0)
            return result

        best_index = max(range(len(remaining)), key=lambda index: score(remaining[index]))
        candidate = remaining.pop(best_index)
        selected.append(candidate)
        for counter, value in zip(selected_counts, attributes(candidate)):
            counter[value] += 1

    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, choices=range(1, 884), default=100)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    records = json.loads(args.input.read_text(encoding="utf-8"))
    sample = balanced_sample(records, args.size, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "source": str(args.input),
        "output": str(args.output),
        "seed": args.seed,
        "sample_size": args.size,
        "population_size": len(records),
        "population_distribution": _distribution(records),
        "sample_distribution": _distribution(sample),
        "example_ids": [str(item.get("id") or item.get("filename")) for item in sample],
    }
    report_path = args.report or args.output.with_suffix(".distribution.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
