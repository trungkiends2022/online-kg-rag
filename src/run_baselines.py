"""Run controlled HybridQA/FinQA/HiTab baselines with a common output schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
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
from src.llm.client import capture_llm_metrics, get_provider
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

MANIFEST_SCHEMA_VERSION = 1


def _file_sha256(path: Path) -> str | None:
    """Return a content hash for a regular file, without loading it all at once."""
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_revision(path: Path | None = None) -> str | None:
    """Best-effort revision for code or a checked-out dataset; never raises."""
    command = ["git"]
    if path is not None:
        command.extend(["-C", str(path)])
    command.extend(["rev-parse", "HEAD"])
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None



def _git_worktree_diff_sha256(path: Path | None = None) -> str | None:
    """Hash tracked staged/unstaged changes so uncommitted code cannot mix runs."""
    command = ["git"]
    if path is not None:
        command.extend(["-C", str(path)])
    command.extend(["diff", "--binary", "HEAD"])
    try:
        result = subprocess.run(command, capture_output=True, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def _provider_identity() -> dict[str, str | None]:
    """Capture the effective provider/model without exposing any credentials."""
    configured_name = os.environ.get("LLM_PROVIDER", "anthropic")
    try:
        provider = get_provider()
    except Exception:
        # This keeps local/unit-test runs inspectable. A real model run will
        # still fail later if its provider is not correctly configured.
        return {"provider": configured_name, "model": None}
    return {
        "provider": getattr(provider, "name", configured_name),
        "model": getattr(provider, "model", None),
    }


def _provider_options() -> dict[str, str | None]:
    """Record non-secret provider switches that can alter a model response."""
    option_names = (
        "COMPAT_BASE_URL",
        "OPENROUTER_REASONING_ENABLED",
        "LLM_RATE_LIMIT_RETRIES",
    )
    return {name: os.environ.get(name) for name in option_names}


def _build_run_manifest(args, *, max_workers: int) -> dict:
    """Describe every prediction-affecting input used by one output JSONL."""
    provider = _provider_identity()
    resources = {
        "tables_dir": str(args.tables_dir) if args.tables_dir else None,
        "tables_revision": _git_revision(args.tables_dir) if args.tables_dir else None,
        "tables_worktree_diff_sha256": (
            _git_worktree_diff_sha256(args.tables_dir) if args.tables_dir else None
        ),
        "passages_dir": str(args.passages_dir) if args.passages_dir else None,
        "passages_revision": _git_revision(args.passages_dir) if args.passages_dir else None,
        "passages_worktree_diff_sha256": (
            _git_worktree_diff_sha256(args.passages_dir) if args.passages_dir else None
        ),
        "hitab_tables_dir": str(args.hitab_tables_dir) if args.hitab_tables_dir else None,
        "hitab_tables_revision": (
            _git_revision(args.hitab_tables_dir) if args.hitab_tables_dir else None
        ),
        "hitab_tables_worktree_diff_sha256": (
            _git_worktree_diff_sha256(args.hitab_tables_dir) if args.hitab_tables_dir else None
        ),
    }
    config = {
        "top_k": args.top_k,
        "second_stage_k": args.second_stage_k,
        "max_context_chars": args.max_context_chars,
        "max_output_tokens": args.max_output_tokens,
        "temperature": args.temperature,
        "n_paths": args.n_paths,
        "max_replans": args.max_replans,
        "finqa_table_format": args.finqa_table_format,
        "llm_timeout_seconds": args.llm_timeout_seconds,
        "llm_sdk_retries": args.llm_sdk_retries,
        "max_workers": max_workers,
        "llm_max_concurrent_requests": int(
            os.environ.get(
                f"{os.environ.get('LLM_PROVIDER', '').strip().upper()}_MAX_CONCURRENT_REQUESTS",
                os.environ.get("LLM_MAX_CONCURRENT_REQUESTS", "8"),
            )
        ),
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset": args.dataset,
        "method": args.method,
        "code_worktree_diff_sha256": _git_worktree_diff_sha256(),
        "input": {"path": str(args.input), "sha256": _file_sha256(args.input)},
        "resources": resources,
        "provider": provider,
        "provider_options": _provider_options(),
        "code_revision": _git_revision(),
        "config": config,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return manifest


def _manifest_path(output: Path) -> Path:
    return output.with_suffix(output.suffix + ".manifest.json")


def _prepare_run_manifest(args, *, max_workers: int) -> tuple[dict, Path]:
    """Write a new manifest or reject a resume whose immutable inputs differ."""
    manifest = _build_run_manifest(args, max_workers=max_workers)
    path = _manifest_path(args.output)
    should_resume = args.resume and (args.output.exists() or path.exists())
    if should_resume:
        if not path.is_file():
            raise ValueError(
                f"Cannot safely resume {args.output}: missing run manifest {path}. "
                "Use a new --output path for this legacy result."
            )
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Cannot safely resume: invalid manifest {path}") from exc
        if existing.get("fingerprint") != manifest["fingerprint"]:
            raise ValueError(
                f"Cannot safely resume {args.output}: model, code, input, dataset resource, "
                "or configuration differs from its manifest. Use a new --output path."
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest, path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("hybridqa", "finqa", "hitab"), required=True)
    parser.add_argument(
        "--method", choices=METHODS, default="online_kg_path_text",
        help="Default: online_kg_path_text (direct text context; no code/sandbox).",
    )
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
            "or 8; LLM request concurrency is separately bounded."
        ),
    )
    parser.add_argument(
        "--llm-max-concurrent-requests", type=int,
        help="Override the effective provider request limit (default: 8; CLI wins).",
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
        "--force-progress", action="store_true",
        help="Force tqdm progress bar even in non-tty environments.",
    )
    parser.add_argument(
        "--quiet-records", action="store_true",
        help="Do not print raw example JSON to stdout (keeps tqdm progress bar clean).",
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
    if args.llm_max_concurrent_requests is not None:
        if args.llm_max_concurrent_requests < 1:
            raise ValueError("--llm-max-concurrent-requests must be at least 1")
        os.environ["LLM_MAX_CONCURRENT_REQUESTS"] = str(args.llm_max_concurrent_requests)
        # A command-line setting must also override a provider-specific value
        # loaded from .env (for example GROQ_MAX_CONCURRENT_REQUESTS).
        provider_name = os.environ.get("LLM_PROVIDER", "").strip().upper()
        if provider_name:
            os.environ[f"{provider_name}_MAX_CONCURRENT_REQUESTS"] = str(
                args.llm_max_concurrent_requests
            )
    max_workers = args.max_workers
    if max_workers is None:
        max_workers = int(os.environ.get("BENCHMARK_MAX_WORKERS", "8"))
    if max_workers < 1:
        raise ValueError("--max-workers and BENCHMARK_MAX_WORKERS must be at least 1")
    completed, mode = set(), "w"
    run_manifest, manifest_path = _prepare_run_manifest(args, max_workers=max_workers)

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
            disable_progress = args.no_progress or (not args.force_progress and not sys.stderr.isatty())
            with tqdm(
                total=len(pending),
                desc=f"{args.dataset}/{args.method}",
                unit="sample",
                dynamic_ncols=True,
                disable=disable_progress,
            ) as progress:
                done_count = 0
                em_acc = 0.0
                calls_acc = 0.0
                for record in records_to_write:
                    output.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    output.flush()
                    if not args.quiet_records:
                        print(json.dumps(record, ensure_ascii=False, default=str))
                    done_count += 1
                    em_acc += float(record.get("exact_match") or 0.0)
                    calls_acc += float(record.get("llm_calls") or 0.0)
                    if not disable_progress:
                        progress.set_postfix(
                            em=f"{100 * em_acc / done_count:.1f}%",
                            avg_calls=f"{calls_acc / done_count:.1f}",
                            refresh=False,
                        )
                    progress.update(1)

    records = [
        json.loads(line)
        for line in args.output.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = {"method": args.method, "dataset": args.dataset, "num_examples": len(records)}
    summary["failed_examples"] = sum(row.get("run_status") == "failed" for row in records)
    summary.update(
        run_manifest=str(manifest_path),
        run_fingerprint=run_manifest["fingerprint"],
        provider=run_manifest["provider"]["provider"],
        model=run_manifest["provider"]["model"],
        code_revision=run_manifest["code_revision"],
        input_sha256=run_manifest["input"]["sha256"],
    )
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
        "llm_max_concurrent_requests": int(
            os.environ.get(
                f"{os.environ.get('LLM_PROVIDER', '').strip().upper()}_MAX_CONCURRENT_REQUESTS",
                os.environ.get("LLM_MAX_CONCURRENT_REQUESTS", "8"),
            )
        ),
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
