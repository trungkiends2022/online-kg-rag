"""Run controlled HybridQA/FinQA baselines with a common output schema."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.baselines import (
    FlatTableBM25Baseline,
    HybridQARAGBaseline,
    OnlineKGPathTextBaseline,
    OracleEvidenceBaseline,
    PathConsistencyEvaluator,
    RAGConfig,
)
from src.baselines.hybridqa_rag import BaselineConfig
from src.baselines.metrics import (
    exact_match,
    finqa_execution_match,
    finqa_ratio_percentage_match,
    token_f1,
)
from src.datasets import load_finqa, load_hybridqa
from src.pipeline import OnlineKGPipeline
from src.llm.client import capture_llm_metrics
from src.evaluation.ir_metrics import numerical_ir_metrics


METHODS = (
    "direct_llm",
    "flat_table_bm25",
    "online_kg_path_text",
    "oracle_evidence",
    "path_consistency",
    "numerical_ir",
    "online_kg",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("hybridqa", "finqa"), required=True)
    parser.add_argument("--method", choices=METHODS, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tables-dir", type=Path)
    parser.add_argument("--passages-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--example-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=24_000)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--n-paths", type=int, default=5)
    parser.add_argument("--max-replans", type=int, default=2)
    parser.add_argument(
        "--finqa-table-format", choices=("official", "raw"), default="official",
        help="Use FinQA table (official) or table_ori (raw hierarchical input).",
    )
    parser.add_argument("--resume", action="store_true")
    return parser


def _examples(args):
    if args.dataset == "hybridqa":
        return load_hybridqa(
            args.input,
            tables_dir=args.tables_dir,
            passages_dir=args.passages_dir,
        )
    return load_finqa(args.input, table_format=args.finqa_table_format)


def _make_method(args):
    rag_config = RAGConfig(
        top_k=args.top_k,
        max_context_chars=args.max_context_chars,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
    )
    if args.method == "direct_llm":
        return HybridQARAGBaseline(BaselineConfig(
            passage_top_k=args.top_k,
            max_context_chars=args.max_context_chars,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
        ))
    if args.method == "flat_table_bm25":
        return FlatTableBM25Baseline(rag_config)
    if args.method == "online_kg_path_text":
        return OnlineKGPathTextBaseline(rag_config, n_paths=args.n_paths)
    if args.method == "oracle_evidence":
        return OracleEvidenceBaseline(rag_config)
    pipeline = OnlineKGPipeline(
        temperature=args.temperature,
        execution_mode="numerical_ir" if args.method == "numerical_ir" else "python",
    )
    if args.method == "path_consistency":
        pipeline.evaluator = PathConsistencyEvaluator()
    return pipeline


def _run_method(method, example, args) -> dict:
    if isinstance(method, OnlineKGPipeline):
        prediction = method.run(
            **example.pipeline_inputs(),
            n_paths=args.n_paths,
            max_replans=args.max_replans,
            retrieval_top_k=args.top_k,
        )
    else:
        prediction = method.run(example)
    prediction["method"] = args.method
    return prediction


def main() -> None:
    args = build_parser().parse_args()
    method = _make_method(args)
    completed, mode = set(), "w"
    if args.resume and args.output.exists():
        mode = "a"
        completed = {
            json.loads(line)["id"]
            for line in args.output.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    processed = 0
    with args.output.open(mode, encoding="utf-8") as output:
        for example in _examples(args):
            if args.example_id and example.example_id != args.example_id:
                continue
            if example.example_id in completed:
                continue
            if args.limit is not None and processed >= args.limit:
                break
            started = time.perf_counter()
            with capture_llm_metrics() as performance:
                prediction = _run_method(method, example, args)
            wall_time_ms = round((time.perf_counter() - started) * 1000, 2)
            performance["llm_latency_ms"] = round(performance["llm_latency_ms"], 2)
            performance["wall_time_ms"] = wall_time_ms
            performance["non_llm_time_ms"] = round(
                max(wall_time_ms - performance["llm_latency_ms"], 0.0), 2
            )
            # Provider-neutral interface currently exposes characters, not billed
            # tokenizer counts. Keep this explicit instead of reporting estimates.
            performance["input_tokens"] = None
            performance["output_tokens"] = None
            prediction.update(performance)
            answer = prediction.get("answer")
            record = {
                "id": example.example_id,
                "question": example.question,
                "gold_answer": example.answer,
                **prediction,
            }
            if args.dataset == "hybridqa":
                record["exact_match"] = exact_match(example.answer, answer)
                record["f1"] = token_f1(example.answer, answer)
                executed = prediction.get("executed_value")
                record["execution_exact_match"] = (
                    exact_match(example.answer, executed) if executed is not None else None
                )
            else:
                record["official_execution_accuracy"] = finqa_execution_match(
                    example.answer, answer
                )
                record["execution_accuracy"] = finqa_ratio_percentage_match(
                    example.answer, answer
                )
                executed = prediction.get("executed_value")
                record["path_execution_accuracy"] = (
                    finqa_ratio_percentage_match(example.answer, executed)
                    if executed is not None else None
                )
                record["official_path_execution_accuracy"] = (
                    finqa_execution_match(example.answer, executed)
                    if executed is not None else None
                )
                record["program_accuracy"] = None
                if args.method == "numerical_ir":
                    diagnostics = prediction.get("candidate_diagnostics", [])
                    record["ir_parse_rate"] = (
                        sum(bool(item.get("ir_parse_valid")) for item in diagnostics) / len(diagnostics)
                        if diagnostics else 0.0
                    )
                    record["schema_validity_rate"] = (
                        sum(bool(item.get("schema_valid")) for item in diagnostics) / len(diagnostics)
                        if diagnostics else 0.0
                    )
                    record["execution_success_rate"] = (
                        sum(bool(item.get("success")) for item in diagnostics) / len(diagnostics)
                        if diagnostics else 0.0
                    )
                    ir_detail = numerical_ir_metrics(
                        prediction.get("best_program"),
                        prediction.get("best_step_values"),
                        example.metadata.get("program"),
                        prediction.get("best_evidence", []),
                        example.metadata.get("gold_evidence"),
                    )
                    record.update(ir_detail)
                    if record["execution_accuracy"] == 1:
                        record["error_category"] = None
                    elif record["schema_validity_rate"] == 0:
                        record["error_category"] = "serialization_schema"
                    elif record["execution_success_rate"] == 0:
                        record["error_category"] = "arithmetic_execution"
                    elif ir_detail.get("grounding_recall") is not None and ir_detail["grounding_recall"] < 1:
                        record["error_category"] = "grounding"
                    elif ir_detail.get("operator_accuracy") is not None and ir_detail["operator_accuracy"] < 1:
                        record["error_category"] = "operator_or_composition"
                    elif record["path_execution_accuracy"] == 1 and record["execution_accuracy"] == 0:
                        record["error_category"] = "answer_rendering"
                    elif record["execution_accuracy"] == 0:
                        record["error_category"] = "unit_scale_or_unclassified"
                    else:
                        record["error_category"] = None
            output.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            output.flush()
            print(json.dumps(record, ensure_ascii=False, default=str))
            processed += 1

    records = [
        json.loads(line)
        for line in args.output.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = {"method": args.method, "dataset": args.dataset, "num_examples": len(records)}
    if args.dataset == "hybridqa":
        em = sum(row["exact_match"] for row in records) / len(records) if records else 0.0
        f1 = sum(row["f1"] for row in records) / len(records) if records else 0.0
        summary.update(exact_match=em, f1=f1, exact_match_percent=100 * em, f1_percent=100 * f1)
    else:
        execution = (
            sum(row["execution_accuracy"] for row in records) / len(records)
            if records else 0.0
        )
        official_execution = (
            sum(row.get("official_execution_accuracy", 0.0) for row in records) / len(records)
            if records else 0.0
        )
        summary.update(
            execution_accuracy=execution,
            execution_accuracy_percent=100 * execution,
            official_execution_accuracy=official_execution,
            official_execution_accuracy_percent=100 * official_execution,
            ratio_percentage_equivalent=True,
        )
        if args.method == "numerical_ir":
            for key in (
                "ir_parse_rate", "schema_validity_rate", "execution_success_rate",
                "operator_accuracy", "step_accuracy", "grounding_precision", "grounding_recall",
            ):
                values = [float(row[key]) for row in records if row.get(key) is not None]
                summary[f"mean_{key}"] = round(sum(values) / len(values), 5) if values else None
            categories: dict[str, int] = {}
            for row in records:
                category = row.get("error_category")
                if category:
                    categories[category] = categories.get(category, 0) + 1
            summary["error_taxonomy"] = categories
    if records:
        for key in (
            "wall_time_ms",
            "llm_latency_ms",
            "non_llm_time_ms",
            "llm_calls",
            "llm_api_attempts",
            "llm_prompt_chars",
            "llm_response_chars",
        ):
            values = [float(row.get(key, 0)) for row in records]
            summary[f"total_{key}"] = round(sum(values), 2)
            summary[f"mean_{key}"] = round(sum(values) / len(values), 2)
    summary["config"] = {
        "top_k": args.top_k,
        "max_context_chars": args.max_context_chars,
        "max_output_tokens": args.max_output_tokens,
        "temperature": args.temperature,
        "n_paths": args.n_paths,
        "max_replans": args.max_replans,
        "finqa_table_format": args.finqa_table_format,
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
