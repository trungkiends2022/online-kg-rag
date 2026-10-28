"""Run controlled HybridQA/FinQA/HiTab baselines with a common output schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from src.baselines import (
    FlatTableBM25Baseline,
    HybridQARAGBaseline,
    OnlineKGPathTextBaseline,
    PathTextTopNBaseline,
    OnlineUnifiedEvidenceGraphBaseline,
    OracleEvidenceBaseline,
    PathConsistencyEvaluator,
    GraphRetrievalNoPathBaseline,
    RAGConfig,
    SharedContextFlatRAGBaseline,
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
from src.datasets import load_finqa, load_hitab, load_hybridqa, load_ottqa
from src.pipeline import OnlineKGPipeline
from src.llm.client import capture_llm_metrics, get_provider
from src.evaluation.ir_metrics import numerical_ir_metrics
from src.evaluation.async_logger import AsyncBenchmarkLogger


METHODS = (
    "direct_llm",
    "flat_table_bm25",
    "flat_rag_shared_context",
    "online_kg_path_text",
    "path_text_top_n",
    "odyssey",
    "online_unified_evidence_graph",
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
        "GROQ_REASONING_EFFORT",
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
        "max_table_rows_for_kg": args.max_table_rows_for_kg,
        "max_output_tokens": args.max_output_tokens,
        "temperature": args.temperature,
        "use_rule_text_triples": args.use_rule_text_triples,
        "use_record_nodes": args.use_record_nodes,
        "use_path_guidance": args.use_path_guidance,
        "use_lexical_tiebreak": args.use_lexical_tiebreak,
        "use_hyperlink_expansion": args.use_hyperlink_expansion,
        "use_collision_evidence_expansion": args.use_collision_evidence_expansion,
        "collision_passage_budget": args.collision_passage_budget,
        "use_focus_evidence_augmentation": args.use_focus_evidence_augmentation,
        "focus_passage_budget_per_candidate": args.focus_passage_budget_per_candidate,
        "use_diagnostic_focus_resolution": args.use_diagnostic_focus_resolution,
        "focus_query_fallback_budget": args.focus_query_fallback_budget,
        "l2_existing_witness_budget": args.l2_existing_witness_budget,
        "l2_max_edges_per_candidate": args.l2_max_edges_per_candidate,
        "l2_max_contexts_per_candidate": args.l2_max_contexts_per_candidate,
        "l2_context_snippet_chars": args.l2_context_snippet_chars,
        "use_adaptive_verification": args.use_adaptive_verification,
        "l2_evidence_mode": args.l2_evidence_mode,
        "use_prompt_compression": args.use_prompt_compression,
        "use_path_focused_prompt": args.use_path_focused_prompt,
        "prompt_path_budget": args.prompt_path_budget,
        "ambiguity_policy": args.ambiguity_policy,
        "oueg_context_mode": args.oueg_context_mode,
        "n_paths": args.n_paths,
        "strict_path_text_top_n": args.strict_path_text_top_n,
        "odyssey_max_hops": args.odyssey_max_hops,
        "odyssey_semantic_threshold": args.odyssey_semantic_threshold,
        "max_replans": args.max_replans,
        "finqa_table_format": args.finqa_table_format,
        "llm_timeout_seconds": args.llm_timeout_seconds,
        "llm_sdk_retries": args.llm_sdk_retries,
        "write_completion_order": args.write_completion_order,
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
            essential_match = (
                existing.get("dataset") == manifest["dataset"]
                and existing.get("method") == manifest["method"]
                and existing.get("provider") == manifest["provider"]
                and existing.get("input", {}).get("sha256") == manifest["input"]["sha256"]
                and existing.get("config") == manifest["config"]
            )
            if not essential_match:
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
    parser.add_argument("--dataset", choices=("hybridqa", "finqa", "hitab", "ottqa"), required=True)
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
    parser.add_argument(
        "--max-table-rows-for-kg", type=int,
        help="Maximum table rows used to construct a KG; omit to retain every row (default).",
    )
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument(
        "--llm-timeout-seconds", type=float,
        help="Timeout for one provider request; overrides LLM_REQUEST_TIMEOUT_SECONDS.",
    )
    parser.add_argument(
        "--llm-sdk-retries", type=int,
        help="Provider SDK retry count; overrides LLM_SDK_MAX_RETRIES.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--no-rule-text-triples", action="store_false", dest="use_rule_text_triples", help="Disable deterministic rule-based text triples when building a KG.")
    parser.add_argument("--no-record-nodes", action="store_false", dest="use_record_nodes", help="OUEG ablation: replace row-record hubs with direct subject--value edges.")
    parser.add_argument("--no-path-guidance", action="store_false", dest="use_path_guidance", help="OUEG ablation: send the full subgraph without suggested paths or ordering guidance.")
    parser.add_argument("--lexical-tiebreak", action="store_true", dest="use_lexical_tiebreak", default=False, help="Historical OUEG ablation: expose lexical collision overlap as a weak reader hint; disabled by default because it is not evidence.")
    parser.add_argument("--no-lexical-tiebreak", action="store_false", dest="use_lexical_tiebreak", help="Deprecated compatibility flag; lexical tie-break is already disabled by default.")
    parser.add_argument("--no-hyperlink-expansion", action="store_false", dest="use_hyperlink_expansion", help="Ablation: disable selected-row and witness hyperlink passage expansion in stage two.")
    parser.add_argument("--no-collision-evidence-expansion", action="store_false", dest="use_collision_evidence_expansion", help="OUEG ablation: do not add linked passages for every candidate in a score collision.")
    parser.add_argument("--collision-passage-budget", type=int, default=12, help="OUEG: maximum linked passages added for a score-collision candidate set.")
    parser.add_argument("--no-focus-evidence-augmentation", action="store_false", dest="use_focus_evidence_augmentation", help="OUEG ablation: do not retrieve candidate-linked passages after an L1 missing-link or insufficient-evidence diagnostic.")
    parser.add_argument("--focus-passage-budget-per-candidate", type=int, default=2, help="OUEG: linked-passage budget for each validated L2 focus candidate.")
    parser.add_argument("--no-diagnostic-focus-resolution", action="store_false", dest="use_diagnostic_focus_resolution", help="OUEG ablation: fall back to structural row anchors instead of grounding L1 diagnostics in table values.")
    parser.add_argument("--focus-query-fallback-budget", type=int, default=2, help="OUEG: per-focus lexical fallback passages from the supplied example corpus.")
    parser.add_argument("--l2-existing-witness-budget", type=int, default=2, help="OUEG: L1-visible passages retained in the small L2 capsule for its needed_check.")
    parser.add_argument("--l2-max-edges-per-candidate", type=int, default=16, help="OUEG: evidence-edge cap for each L2 candidate packet.")
    parser.add_argument("--l2-max-contexts-per-candidate", type=int, default=3, help="OUEG: passage cap for each L2 candidate packet.")
    parser.add_argument("--l2-context-snippet-chars", type=int, default=900, help="OUEG: maximum chars for each L2 passage snippet.")
    parser.add_argument("--no-adaptive-verification", action="store_false", dest="use_adaptive_verification", help="OUEG ablation: disable the diagnostic-triggered L2 recovery branch after an empty or NEED_FOCUS response.")
    parser.add_argument("--l2-evidence-mode", choices=("delta_only", "complete_re_read"), default="delta_only", help="OUEG L2 context: small sufficient state capsule (default) or full-graph diagnostic ablation.")
    parser.add_argument("--no-prompt-compression", action="store_false", dest="use_prompt_compression", help="OUEG ablation: serialize the full uncompressed evidence payload.")
    parser.add_argument("--path-focused-prompt", action="store_true", dest="use_path_focused_prompt", help="OUEG ablation: prune the L1 reader payload to path-focused evidence instead of the full compact OUEG.")
    parser.add_argument("--no-path-focused-prompt", action="store_false", dest="use_path_focused_prompt", help="Deprecated compatibility flag; Full OUEG already uses the complete compact L1 graph.")
    parser.set_defaults(use_path_focused_prompt=False)
    parser.add_argument("--prompt-path-budget", type=int, default=8, help="OUEG: maximum grounded path guides retained in the answer-time payload (default: 8).")
    parser.add_argument(
        "--ambiguity-policy", choices=("prompt", "return_candidates", "lexical_tiebreak"), default="prompt",
        help="OUEG ambiguity handling: expose it to the LLM, return all candidates, or use a unique lexical tie-break.",
    )
    parser.add_argument(
        "--oueg-context-mode", choices=("lossless", "extractive"), default="lossless",
        help="OUEG prompt context serialization; extractive only shortens long contexts.",
    )
    parser.add_argument("--n-paths", type=int, default=5)
    parser.add_argument(
        "--strict-path-text-top-n", action="store_true",
        help=(
            "Path-Text Top-N controlled comparator: expose only selected path "
            "edges and their direct contexts, excluding table retrieval witnesses."
        ),
    )
    parser.add_argument(
        "--odyssey-max-hops", type=int, default=3,
        help="ODYSSEY: maximum hop-wise reader iterations (1--3; default 3).",
    )
    parser.add_argument(
        "--odyssey-semantic-threshold", type=float, default=0.8,
        help="ODYSSEY: minimum semantic-match score used to seed BFS (default 0.8).",
    )
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
        "--write-completion-order", action="store_true",
        help="Write parallel examples as they complete; supports resume in short-lived sessions.",
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
    if args.dataset == "ottqa":
        if args.tables_dir is None:
            raise ValueError("OTT-QA requires --tables-dir")
        return load_ottqa(
            args.input,
            tables_dir=args.tables_dir,
            passages_dir=args.passages_dir,
            example_id=args.example_id,
        )
    tables_dir = args.hitab_tables_dir or args.tables_dir
    if tables_dir is None:
        raise ValueError("HiTab requires --hitab-tables-dir or --tables-dir")
    return load_hitab(args.input, tables_dir=tables_dir)


def _make_method(args):
    rag_config = RAGConfig(
        top_k=args.top_k,
        second_stage_k=args.second_stage_k,
        max_table_rows_for_kg=args.max_table_rows_for_kg,
        max_context_chars=args.max_context_chars,
        use_rule_text_triples=args.use_rule_text_triples,
        use_record_nodes=args.use_record_nodes,
        use_path_guidance=args.use_path_guidance,
        use_lexical_tiebreak=args.use_lexical_tiebreak,
        use_hyperlink_expansion=args.use_hyperlink_expansion,
        use_collision_evidence_expansion=args.use_collision_evidence_expansion,
        collision_passage_budget=args.collision_passage_budget,
        use_focus_evidence_augmentation=args.use_focus_evidence_augmentation,
        focus_passage_budget_per_candidate=args.focus_passage_budget_per_candidate,
        use_diagnostic_focus_resolution=args.use_diagnostic_focus_resolution,
        focus_query_fallback_budget=args.focus_query_fallback_budget,
        l2_existing_witness_budget=args.l2_existing_witness_budget,
        l2_max_edges_per_candidate=args.l2_max_edges_per_candidate,
        l2_max_contexts_per_candidate=args.l2_max_contexts_per_candidate,
        l2_context_snippet_chars=args.l2_context_snippet_chars,
        use_adaptive_verification=args.use_adaptive_verification,
        l2_evidence_mode=args.l2_evidence_mode,
        use_prompt_compression=args.use_prompt_compression,
        use_path_focused_prompt=args.use_path_focused_prompt,
        prompt_path_budget=args.prompt_path_budget,
        ambiguity_policy=args.ambiguity_policy,
        oueg_context_mode=args.oueg_context_mode,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
    )
    if args.method == "direct_llm":
        return HybridQARAGBaseline(BaselineConfig(
            passage_top_k=args.top_k,
            max_context_chars=args.max_context_chars,
            max_output_tokens=args.max_output_tokens,
            second_stage_k=args.second_stage_k,
            temperature=args.temperature,
        ))
    if args.method == "flat_table_bm25":
        return FlatTableBM25Baseline(rag_config)
    if args.method == "flat_rag_shared_context":
        return SharedContextFlatRAGBaseline(rag_config)
    if args.method == "graph_retrieval_no_path":
        return GraphRetrievalNoPathBaseline(rag_config)
    if args.method == "online_kg_path_text":
        return OnlineKGPathTextBaseline(rag_config, n_paths=args.n_paths)
    if args.method == "path_text_top_n":
        return PathTextTopNBaseline(
            rag_config,
            n_paths=args.n_paths,
            strict_path_only=args.strict_path_text_top_n,
        )
    if args.method == "odyssey":
        from src.baselines.odyssey import OdysseyBaseline, OdysseyConfig
        return OdysseyBaseline(
            rag_config,
            OdysseyConfig(
                max_hops=args.odyssey_max_hops,
                semantic_threshold=args.odyssey_semantic_threshold,
            ),
        )
    if args.method == "online_unified_evidence_graph":
        return OnlineUnifiedEvidenceGraphBaseline(rag_config)
    if args.method == "oracle_evidence":
        return OracleEvidenceBaseline(rag_config)
    pipeline = OnlineKGPipeline(
        max_table_rows_for_kg=args.max_table_rows_for_kg,
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

def _hybridqa_retrieval_audit(example, prediction: dict) -> dict:
    """Evaluate retrieval only when HybridQA traced answer-node evidence exists."""
    nodes = example.metadata.get("answer_nodes", [])
    if not nodes:
        return {"gold_row_recall": None, "gold_hyperlink_recall": None, "gold_passage_recall": None}
    gold_rows, gold_links = set(), set()
    for node in nodes:
        if not isinstance(node, (list, tuple)):
            continue
        if len(node) > 1 and isinstance(node[1], (list, tuple)) and node[1]:
            gold_rows.add(int(node[1][0]))
        if len(node) > 2 and node[2]:
            gold_links.add(str(node[2]).casefold())
    trace = prediction.get("retrieval_trace", {})
    selected_rows = set(trace.get("selected_table_row_indices", []))
    selected_passages = {
        str(value).casefold() for value in prediction.get("retrieved_passage_ids", [])
    }
    selected_links = {
        str(value).casefold() for value in trace.get("selected_row_hyperlinks", [])
    }
    return {
        "gold_row_recall": float(bool(gold_rows) and gold_rows <= selected_rows) if gold_rows else None,
        "gold_hyperlink_recall": float(bool(gold_links) and gold_links <= selected_links) if gold_links else None,
        "gold_passage_recall": float(bool(gold_links) and gold_links <= selected_passages) if gold_links else None,
    }


def _hybridqa_error_category(record: dict) -> str | None:
    if record["exact_match"]:
        return None
    if not str(record.get("answer") or "").strip():
        return "output_format"
    if record.get("table_truncated"):
        return "table_context_budget"
    if record.get("final_judge_valid") is False:
        return "judge_contract"
    if any(value == 0.0 for key, value in record.get("retrieval_audit", {}).items()
           if key.startswith("gold_")):
        return "retrieval_miss"
    if re.search(r"\b(?:how many|how much|what year|which year)\b", record["question"], re.I):
        return "numeric_or_temporal_reasoning"
    if record.get("reasoning_paths"):
        return "wrong_hop_or_path_selection"
    if record.get("f1", 0) > 0:
        return "format_or_normalization"
    return "retrieval_or_reasoning"


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
    if args.dataset in {"hybridqa", "ottqa"}:
        record["exact_match"] = exact_match(example.answer, answer)
        record["semantic_exact_match"] = semantic_exact_match(
            example.answer, answer, question=example.question,
        )
        record["f1"] = token_f1(example.answer, answer)
        executed = prediction.get("executed_value")
        record["execution_exact_match"] = (
            exact_match(example.answer, executed) if executed is not None else None
        )
        record["retrieval_audit"] = _hybridqa_retrieval_audit(example, prediction)
        record["error_category"] = _hybridqa_error_category(record)
        ambiguity = prediction.get("ambiguity")
        if isinstance(ambiguity, dict):
            record["is_ambiguous"] = bool(ambiguity.get("is_ambiguous", False))
            record["ambiguity_status"] = ambiguity.get("status")
        else:
            record["is_ambiguous"] = None
            record["ambiguity_status"] = None
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

    completed: set[str] = set()
    initial_records: list[dict] = []
    if args.resume and args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                qid = rec.get("id") or rec.get("question_id")
                if qid:
                    completed.add(str(qid))
                initial_records.append(rec)
            except Exception:
                continue

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

    logger = AsyncBenchmarkLogger(
        output_path=args.output,
        total_pending=len(pending),
        args=args,
        run_manifest=run_manifest,
        manifest_path=manifest_path,
        max_workers=max_workers,
        initial_records=initial_records,
    )

    try:
        if pending:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(pending))) as executor:
                futures = {
                    executor.submit(_evaluate_example, example, args): seq_idx
                    for seq_idx, example in enumerate(pending)
                }
                for future in as_completed(futures):
                    seq_idx = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        if args.fail_fast:
                            raise
                        record = {
                            "id": pending[seq_idx].example_id,
                            "question": pending[seq_idx].question,
                            "gold_answer": pending[seq_idx].answer,
                            "answer": None,
                            "error": f"{type(exc).__name__}: {exc}",
                            "run_status": "failed",
                        }
                    logger.log_record(seq_idx, record)
    finally:
        logger.close()


if __name__ == "__main__":
    main()
