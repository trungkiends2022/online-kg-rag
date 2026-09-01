"""Run a small benchmark slice through the online-KG pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.datasets import load_finqa, load_hybridqa
from src.pipeline import OnlineKGPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("hybridqa", "finqa"), required=True)
    parser.add_argument("--input", type=Path, required=True, help="Dataset split JSON")
    parser.add_argument("--tables-dir", type=Path, help="HybridQA external table directory")
    parser.add_argument("--passages-dir", type=Path, help="HybridQA external passage directory")
    parser.add_argument("--limit", type=int, default=10, help="Maximum examples (default: 10)")
    parser.add_argument("--output", type=Path, help="Write JSONL here instead of stdout")
    parser.add_argument("--n-paths", type=int, default=5)
    parser.add_argument("--max-replans", type=int, default=2)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.dataset == "hybridqa":
        examples = load_hybridqa(
            args.input,
            tables_dir=args.tables_dir,
            passages_dir=args.passages_dir,
            limit=args.limit,
        )
    else:
        examples = load_finqa(args.input, limit=args.limit)

    pipeline = OnlineKGPipeline()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    output_handle = args.output.open("w", encoding="utf-8") if args.output else None
    try:
        for example in examples:
            prediction = pipeline.run(
                **example.pipeline_inputs(),
                n_paths=args.n_paths,
                max_replans=args.max_replans,
            )
            record = {
                "id": example.example_id,
                "question": example.question,
                "gold_answer": example.answer,
                "metadata": example.metadata,
                **prediction,
            }
            line = json.dumps(record, ensure_ascii=False, default=str)
            if output_handle:
                output_handle.write(line + "\n")
                output_handle.flush()
            else:
                print(line)
    finally:
        if output_handle:
            output_handle.close()


if __name__ == "__main__":
    main()
