"""Audit FinQA modality mix, retrieval coverage, and table conversion safety."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.datasets.common import matrix_to_rows, read_json
from src.retrieval.coarse_retrieval import _tokenize


def _normalize(text) -> str:
    return " ".join(str(text).lower().split())


def audit(path: Path, top_k: int = 5) -> dict:
    records = read_json(path)
    modalities = Counter()
    text_required = text_retrieved = unmatched_gold = 0
    lossy_raw_tables = duplicate_headers = yes_no = 0

    for item in records:
        qa = item.get("qa", {})
        gold = qa.get("gold_inds") or {}
        table_gold = any(str(key).startswith("table") for key in gold)
        text_gold = any(not str(key).startswith("table") for key in gold)
        mode = "both" if table_gold and text_gold else (
            "table_only" if table_gold else "text_only" if text_gold else "none"
        )
        modalities[mode] += 1
        if str(qa.get("exe_ans", "")).strip().lower() in {"yes", "no"}:
            yes_no += 1

        if text_gold:
            text_required += 1
            passages = [str(value) for value in item.get("pre_text", []) + item.get("post_text", [])]
            gold_text = {
                _normalize(value) for key, value in gold.items()
                if not str(key).startswith("table")
            }
            matched = {
                next((index for index, text in enumerate(passages) if _normalize(text) == value), None)
                for value in gold_text
            }
            if None in matched:
                unmatched_gold += 1
            elif passages:
                scores = BM25Okapi([_tokenize(text) for text in passages]).get_scores(
                    _tokenize(qa.get("question", ""))
                )
                selected = set(sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)[:top_k])
                if matched <= selected:
                    text_retrieved += 1

        raw = item.get("table_ori") or []
        if raw:
            converted = matrix_to_rows(raw)
            output_width = max((len(row) for row in converted), default=0)
            input_width = max((len(row) for row in raw[1:]), default=0)
            if output_width < input_width:
                lossy_raw_tables += 1
            header = [str(value).strip() for value in raw[0]]
            if len(header) != len(set(header)):
                duplicate_headers += 1

    total = len(records)
    return {
        "dataset_path": str(path),
        "num_examples": total,
        "modality_counts": dict(modalities),
        "modality_percent": {
            key: round(100 * value / total, 2) if total else 0.0
            for key, value in modalities.items()
        },
        "text_required": text_required,
        f"all_gold_text_recall_at_{top_k}": round(
            text_retrieved / text_required, 6
        ) if text_required else 1.0,
        "unmatched_gold_text_records": unmatched_gold,
        "raw_table_width_loss_records": lossy_raw_tables,
        "raw_duplicate_first_header_records": duplicate_headers,
        "yes_no_answers": yes_no,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.input, args.top_k)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
