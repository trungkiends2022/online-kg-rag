"""Run controlled HybridQA/FinQA/HiTab baselines with a common output schema."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tqdm import tqdm

from src.baselines import (
    FlatTableBM25Baseline,
    HybridQARAGBaseline,
    OnlineKGPathTextBaseline,
    OracleEvidenceBaseline,
    PathConsistencyEvaluator,
    GraphRetrievalNoPathBaseline,
    RAGConfig,
)
from src.baselines.hybridqa_rag import BaselineConfig
from src.baselines.metrics import (
    exact_match,
    semantic_exact_match,
    finqa_execution_match,
    finqa_ratio_percentage_match,
    hitab_denotation_match,
    hitab_strict_denotation_match,
    token_f1,
)
from src.datasets import load_finqa, load_hitab, load_hybridqa
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
    "graph_retrieval_no_path",
    "online_kg",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("hybridqa", "finqa", "hitab"), required=True)
    parser.add_argument("--method", choices=METHODS, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tables-dir", type=Path)
    parser.add_argument("--passages-dir", type=Path)
    parser.add_argument("--hitab-tables-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--example-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--second-stage-k", type=int, default=3)
    parser.add_argument("--max-context-chars", type=int, default=24_000)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument(
        "--llm-timeout-seconds", type=float,
        help="Timeout for one provider request; overrides LLM_REQUEST_TIMEOUT_SECONDS.",
    )
    parser.add_argument(
        "--llm-sdk-retries", type=int,
        help="Provider SDK retry count; overrides LLM_SDK_MAX_RETRIES.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--n-paths", type=int, default=5)
    parser.add_argument("--max-replans", type=int, default=2)
    parser.add_argument(
        "--max-workers", type=int,
        help=(
            "Concurrent independent samples. Defaults to BENCHMARK_MAX_WORKERS "
            "or 1; provider rate limits still apply."
        ),
    )
    parser.add_argument(
        "--finqa-table-format", choices=("official", "raw"), default="official",
        help="Use FinQA table (official) or table_ori (raw hierarchical input).",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--no-progress", action="store_true",
        help="Disable the tqdm progress bar (useful for machine-readable logs).",
    )
    parser.add_argument(
        "--fail-fast", action="store_true",
        help="stop before recording a failed example; useful for resumable long server runs",
    )
    return parser


def _examples(args):
    if args.dataset == "hybridqa":
        return load_hybridqa(
            args.input,
            tables_dir=args.tables_dir,
            passages_dir=args.passages_dir,
            example_id=args.example_id,
        )
    if args.dataset == "finqa":
        return load_finqa(args.input, table_format=args.finqa_table_format)
    tables_dir = args.hitab_tables_dir or args.tables_dir
    if tables_dir is None:
        raise ValueError("HiTab requires --hitab-tables-dir or --tables-dir")
    return load_hitab(args.input, tables_dir=tables_dir)


def _make_method(args):
    rag_config = RAGConfig(
        top_k=args.top_k,
        second_stage_k=args.second_stage_k,
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
    if args.method == "graph_retrieval_no_path":
        return GraphRetrievalNoPathBaseline(rag_config)
    if args.method == "online_kg_path_text":
        return OnlineKGPathTextBaseline(rag_config, n_paths=args.n_paths)
    if args.method == "oracle_evidence":
        return OracleEvidenceBaseline(rag_config)
    pipeline = OnlineKGPipeline(
        temperature=args.temperature,
        execution_mode="numerical_ir" if args.method == "numerical_ir" else "python",
        finqa_canonical_ratio=(args.dataset == "finqa" and args.method == "numerical_ir"),
        max_output_tokens=args.max_output_tokens,
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
            retrieval_second_stage_k=args.second_stage_k,
        )
    else:
        prediction = method.run(example)
    prediction["method"] = args.method
    return prediction


def _evaluate_example(example, args) -> dict:
    """Run one sample with isolated mutable pipeline state and collect its record."""
    started = time.perf_counter()
    with capture_llm_metrics() as performance:
        try:
            # OnlineKGPipeline keeps diagnostics from its last run.  Do not share
            # it between workers, even though the underlying HTTP client is shared.
            prediction = _run_method(_make_method(args), example, args)
        except Exception as exc:  # one bad model response must not stop a dataset run
            if args.fail_fast:
                raise
            prediction = {
                "answer": None,
                "executed_value": None,
                "error": f"{type(exc).__name__}: {exc}",
                "fatal_error_type": type(exc).__name__,
                "run_status": "failed",
                "method": args.method,
                "execution_mode": (
                    "numerical_ir" if args.method == "numerical_ir" else None
                ),
                "candidate_diagnostics": [],
            }
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
        record["semantic_exact_match"] = semantic_exact_match(example.answer, answer)
        record["f1"] = token_f1(example.answer, answer)
        executed = prediction.get("executed_value")
        record["execution_exact_match"] = (
            exact_match(example.answer, executed) if executed is not None else None
        )
    elif args.dataset == "finqa":
        _add_finqa_metrics(record, prediction, example, args)
    else:
        record["official_denotation_accuracy"] = hitab_strict_denotation_match(
            example.answer, answer
        )
        record["denotation_accuracy"] = hitab_denotation_match(example.answer, answer)
        executed = prediction.get("executed_value")
        record["official_path_denotation_accuracy"] = (
            hitab_strict_denotation_match(example.answer, executed)
            if executed is not None else None
        )
        record["path_denotation_accuracy"] = (
            hitab_denotation_match(example.answer, executed)
            if executed is not None else None
        )
    return record


def _add_finqa_metrics(record: dict, prediction: dict, example, args) -> None:
    """Attach FinQA metrics after a worker has produced one prediction."""
    answer = prediction.get("answer")
    record["official_execution_accuracy"] = finqa_execution_match(example.answer, answer)
    record["execution_accuracy"] = finqa_ratio_percentage_match(example.answer, answer)
    executed = prediction.get("executed_value")
    record["path_execution_accuracy"] = (
        finqa_ratio_percentage_match(example.answer, executed)
        if executed is not None else None
    )
    record["official_path_execution_accuracy"] = (
        finqa_execution_match(example.answer, executed) if executed is not None else None
    )
    record["program_accuracy"] = None
    if args.method != "numerical_ir":
        return
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
        prediction.get("best_program"), prediction.get("best_step_values"),
        example.metadata.get("program"), prediction.get("best_evidence", []),
        example.metadata.get("gold_evidence"), question=example.question,
    )
    record.update(ir_detail)
    record["ir_repair_count"] = (prediction.get("best_program") or {}).get("repair_count", 0)
    if prediction.get("run_status") == "failed":
        error_text = f"{prediction.get('fatal_error_type', '')} {prediction.get('error', '')}".lower()
        record["error_category"] = "serialization_schema" if "json" in error_text or "decode" in error_text else "pipeline_failure"
    elif record["execution_accuracy"] == 1:
        record["error_category"] = None
    elif record["schema_validity_rate"] == 0:
        record["error_category"] = "serialization_schema"
    elif record["execution_success_rate"] == 0:
        record["error_category"] = "arithmetic_execution"
    elif ir_detail.get("grounding_precision") is not None and ir_detail["grounding_precision"] < 1:
        record["error_category"] = "grounding"
    elif ir_detail.get("grounding_recall") is not None and ir_detail["grounding_recall"] < 1 and ir_detail.get("operator_accuracy") is not None and ir_detail["operator_accuracy"] < 1:
        record["error_category"] = "operand_or_operator_selection"
    elif ir_detail.get("grounding_recall") is not None and ir_detail["grounding_recall"] < 1:
        record["error_category"] = "operand_selection"
    elif ir_detail.get("operator_accuracy") is not None and ir_detail["operator_accuracy"] < 1:
        record["error_category"] = "operator_selection"
    elif record["path_execution_accuracy"] == 1 and record["execution_accuracy"] == 0:
        record["error_category"] = "answer_rendering"
    elif record["execution_accuracy"] == 0:
        record["error_category"] = "unit_scale_or_unclassified"
    else:
        record["error_category"] = None


def main() -> None:
    args = build_parser().parse_args()
    if args.llm_timeout_seconds is not None:
        if args.llm_timeout_seconds <= 0:
            raise ValueError("--llm-timeout-seconds must be positive")
        os.environ["LLM_REQUEST_TIMEOUT_SECONDS"] = str(args.llm_timeout_seconds)
    if args.llm_sdk_retries is not None:
        if args.llm_sdk_retries < 0:
            raise ValueError("--llm-sdk-retries must be non-negative")
        os.environ["LLM_SDK_MAX_RETRIES"] = str(args.llm_sdk_retries)
    max_workers = args.max_workers
    if max_workers is None:
        max_workers = int(os.environ.get("BENCHMARK_MAX_WORKERS", "1"))
    if max_workers < 1:
        raise ValueError("--max-workers and BENCHMARK_MAX_WORKERS must be at least 1")
    completed, mode = set(), "w"
    if args.resume and args.output.exists():
        mode = "a"
        completed = {
            json.loads(line)["id"]
            for line in args.output.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = []
    for example in _examples(args):
        if args.example_id and example.example_id != args.example_id:
            continue
        if example.example_id in completed:
            continue
        if args.limit is not None and len(pending) >= args.limit:
            break
        pending.append(example)

    with args.output.open(mode, encoding="utf-8") as output:
        # executor.map yields in input order: reproducible JSONL/resume behaviour,
        # while requests themselves run concurrently.
        with ThreadPoolExecutor(max_workers=min(max_workers, len(pending) or 1)) as executor:
            records_to_write = executor.map(lambda example: _evaluate_example(example, args), pending)
            with tqdm(
                total=len(pending),
                desc=f"{args.dataset}/{args.method}",
                unit="sample",
                dynamic_ncols=True,
                disable=args.no_progress or not sys.stderr.isatty(),
            ) as progress:
                for record in records_to_write:
                    output.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    output.flush()
                    print(json.dumps(record, ensure_ascii=False, default=str))
                    progress.update(1)

    records = [
        json.loads(line)
        for line in args.output.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = {"method": args.method, "dataset": args.dataset, "num_examples": len(records)}
    summary["failed_examples"] = sum(row.get("run_status") == "failed" for row in records)
    if args.dataset == "hybridqa":
        em = sum(row["exact_match"] for row in records) / len(records) if records else 0.0
        f1 = sum(row["f1"] for row in records) / len(records) if records else 0.0
        summary.update(exact_match=em, f1=f1, exact_match_percent=100 * em, f1_percent=100 * f1)
        semantic_em = sum(row["semantic_exact_match"] for row in records) / len(records) if records else 0.0
        summary.update(semantic_exact_match=semantic_em, semantic_exact_match_percent=100 * semantic_em)
    elif args.dataset == "finqa":
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
                "strict_operator_accuracy", "strict_step_accuracy",
                "ir_repair_count",
            ):
                values = [float(row[key]) for row in records if row.get(key) is not None]
                summary[f"mean_{key}"] = round(sum(values) / len(values), 5) if values else None
            categories: dict[str, int] = {}
            for row in records:
                category = row.get("error_category")
                if category:
                    categories[category] = categories.get(category, 0) + 1
            summary["error_taxonomy"] = categories
    else:
        accuracy = (
            sum(row["denotation_accuracy"] for row in records) / len(records)
            if records else 0.0
        )
        summary.update(
            denotation_accuracy=accuracy,
            denotation_accuracy_percent=100 * accuracy,
        )
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
        "second_stage_k": args.second_stage_k,
        "max_workers": max_workers,
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
