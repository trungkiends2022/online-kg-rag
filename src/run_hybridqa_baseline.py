"""Run and score the oracle-context BM25 + direct-LLM HybridQA baseline."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.baselines.hybridqa_rag import BaselineConfig, HybridQARAGBaseline
from src.baselines.metrics import exact_match, token_f1
from src.datasets import load_hybridqa


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tables-dir", type=Path, required=True)
    parser.add_argument("--passages-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--example-id", help="Run only the HybridQA question with this ID")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--passage-top-k", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=24_000)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = BaselineConfig(
        passage_top_k=args.passage_top_k,
        max_context_chars=args.max_context_chars,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
    )
    baseline = HybridQARAGBaseline(config)
    completed = set()
    mode = "w"
    if args.resume and args.output.exists():
        mode = "a"
        for line in args.output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                completed.add(json.loads(line)["id"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    processed = 0
    with args.output.open(mode, encoding="utf-8") as output:
        for example in load_hybridqa(
            args.input,
            tables_dir=args.tables_dir,
            passages_dir=args.passages_dir,
        ):
            if args.example_id and example.example_id != args.example_id:
                continue
            if example.example_id in completed:
                continue
            if args.limit is not None and processed >= args.limit:
                break
            prediction = baseline.run(example)
            record = {
                "id": example.example_id,
                "question": example.question,
                "gold_answer": example.answer,
                **prediction,
            }
            record["exact_match"] = exact_match(example.answer, prediction["answer"])
            record["f1"] = token_f1(example.answer, prediction["answer"])
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            print(json.dumps(record, ensure_ascii=False))
            processed += 1

    records = [
        json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    mean_em = sum(row["exact_match"] for row in records) / len(records) if records else 0.0
    mean_f1 = sum(row["f1"] for row in records) / len(records) if records else 0.0
    summary = {
        "method": baseline.method_name,
        "num_examples": len(records),
        "exact_match": mean_em,
        "f1": mean_f1,
        "exact_match_percent": round(mean_em * 100, 2),
        "f1_percent": round(mean_f1 * 100, 2),
        "config": asdict(config),
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
