#!/usr/bin/env python3
"""Materialise reproducible ambiguity-stratified HybridQA subsets from an OUEG run."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="HybridQA shard JSON array")
    parser.add_argument("--reference", type=Path, required=True, help="Completed OUEG JSONL used only to select ambiguity")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--non-ambiguous-limit", type=int, default=0,
        help="Additionally sample this many reference cases that are not ambiguous.",
    )
    parser.add_argument(
        "--seed", type=int,
        help="Random seed for reproducible sampling. Omit to retain reference order.",
    )
    parser.add_argument("--skip", type=int, default=0, help="Skip this many eligible cases before selecting")
    parser.add_argument("--status", default="SCORE_COLLISION_TIE", help="Ambiguity status; use '*' for every ambiguous case")
    args = parser.parse_args()
    if args.limit < 1 or args.non_ambiguous_limit < 0 or args.skip < 0:
        raise ValueError("--limit must be positive; --non-ambiguous-limit and --skip must not be negative")

    source = json.loads(args.source.read_text(encoding="utf-8"))
    if not isinstance(source, list):
        raise ValueError(f"expected a JSON array in {args.source}")
    source_by_id = {str(row.get("question_id")): row for row in source}
    ambiguous_ids, non_ambiguous_ids = [], []
    for row in _load_jsonl(args.reference):
        ambiguity = row.get("ambiguity") if isinstance(row.get("ambiguity"), dict) else {}
        is_ambiguous = row.get("is_ambiguous") is True or ambiguity.get("is_ambiguous") is True
        status = ambiguity.get("status") or row.get("ambiguity_status")
        identifier = str(row.get("id") or "")
        if identifier not in source_by_id:
            continue
        if is_ambiguous and (args.status == "*" or status == args.status):
            if identifier not in ambiguous_ids:
                ambiguous_ids.append(identifier)
        elif not is_ambiguous and identifier not in non_ambiguous_ids:
            non_ambiguous_ids.append(identifier)

    original_skip = args.skip
    eligible_ambiguous = ambiguous_ids[original_skip:]
    if len(eligible_ambiguous) < args.limit:
        raise ValueError(f"found only {len(eligible_ambiguous)} eligible ambiguous cases, expected {args.limit}")
    if len(non_ambiguous_ids) < args.non_ambiguous_limit:
        raise ValueError(
            f"found only {len(non_ambiguous_ids)} eligible non-ambiguous cases, "
            f"expected {args.non_ambiguous_limit}",
        )
    if args.seed is None:
        selected_ambiguous = eligible_ambiguous[:args.limit]
        selected_non_ambiguous = non_ambiguous_ids[:args.non_ambiguous_limit]
    else:
        generator = random.Random(args.seed)
        selected_ambiguous = generator.sample(eligible_ambiguous, args.limit)
        selected_non_ambiguous = generator.sample(non_ambiguous_ids, args.non_ambiguous_limit)
    selected_ids = selected_ambiguous + selected_non_ambiguous

    selected = [source_by_id[identifier] for identifier in selected_ids]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "source": str(args.source),
        "reference": str(args.reference),
        "ambiguity_status": args.status,
        "seed": args.seed,
        "count": len(selected),
        "strata": {
            "ambiguous": len(selected_ambiguous),
            "non_ambiguous": len(selected_non_ambiguous),
        },
        "ambiguous_question_ids": selected_ambiguous,
        "non_ambiguous_question_ids": selected_non_ambiguous,
        "skip": original_skip,
        "question_ids": selected_ids,
    }
    args.output.with_suffix(args.output.suffix + ".selection.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
