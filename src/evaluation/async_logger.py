"""Asynchronous, non-blocking background logger and real-time metric aggregator for benchmarks."""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

from tqdm import tqdm


def extract_summary_record(record: dict[str, Any]) -> dict[str, Any]:
    """Extract lightweight projection (~300 bytes) of a sample record for summary metrics.
    
    Drops heavy structures (evidence graphs, full passages, serialized states) to prevent
    high RAM usage and avoid slow multi-MB JSON parsing at summary time.
    """
    return {
        "id": record.get("id"),
        "question": record.get("question"),
        "gold_answer": record.get("gold_answer"),
        "answer": record.get("answer"),
        "run_status": record.get("run_status"),
        "exact_match": record.get("exact_match"),
        "semantic_exact_match": record.get("semantic_exact_match"),
        "f1": record.get("f1"),
        "execution_exact_match": record.get("execution_exact_match"),
        "is_ambiguous": record.get("is_ambiguous"),
        "ambiguity_status": record.get("ambiguity_status"),
        "error_category": record.get("error_category"),
        "retrieval_audit": record.get("retrieval_audit"),
        "execution_accuracy": record.get("execution_accuracy"),
        "official_execution_accuracy": record.get("official_execution_accuracy"),
        "denotation_accuracy": record.get("denotation_accuracy"),
        "official_denotation_accuracy": record.get("official_denotation_accuracy"),
        "path_denotation_accuracy": record.get("path_denotation_accuracy"),
        "official_path_denotation_accuracy": record.get("official_path_denotation_accuracy"),
        "ir_parse_rate": record.get("ir_parse_rate"),
        "schema_validity_rate": record.get("schema_validity_rate"),
        "execution_success_rate": record.get("execution_success_rate"),
        "operator_accuracy": record.get("operator_accuracy"),
        "step_accuracy": record.get("step_accuracy"),
        "grounding_precision": record.get("grounding_precision"),
        "grounding_recall": record.get("grounding_recall"),
        "strict_operator_accuracy": record.get("strict_operator_accuracy"),
        "strict_step_accuracy": record.get("strict_step_accuracy"),
        "ir_repair_count": record.get("ir_repair_count"),
        "wall_time_ms": record.get("wall_time_ms", 0),
        "llm_latency_ms": record.get("llm_latency_ms", 0),
        "non_llm_time_ms": record.get("non_llm_time_ms", 0),
        "llm_calls": record.get("llm_calls", 0),
        "llm_api_attempts": record.get("llm_api_attempts", 0),
        "llm_prompt_chars": record.get("llm_prompt_chars", 0),
        "llm_response_chars": record.get("llm_response_chars", 0),
    }


def compute_benchmark_summary(
    records: list[dict[str, Any]],
    args: argparse.Namespace,
    run_manifest: dict[str, Any],
    manifest_path: Path,
    max_workers: int,
) -> dict[str, Any]:
    """Compute benchmark summary dictionary identical to the legacy implementation."""
    summary: dict[str, Any] = {
        "method": args.method,
        "dataset": args.dataset,
        "num_examples": len(records),
        "failed_examples": sum(row.get("run_status") == "failed" for row in records),
        "run_manifest": str(manifest_path),
        "run_fingerprint": run_manifest.get("fingerprint"),
        "provider": run_manifest.get("provider", {}).get("provider"),
        "model": run_manifest.get("provider", {}).get("model"),
        "code_revision": run_manifest.get("code_revision"),
        "input_sha256": run_manifest.get("input", {}).get("sha256"),
    }

    if args.dataset in {"hybridqa", "ottqa"}:
        em = sum(row.get("exact_match") or 0.0 for row in records) / len(records) if records else 0.0
        f1 = sum(row.get("f1") or 0.0 for row in records) / len(records) if records else 0.0
        sem = sum(row.get("semantic_exact_match") or 0.0 for row in records) / len(records) if records else 0.0
        summary.update(
            exact_match=em,
            f1=f1,
            exact_match_percent=100.0 * em,
            f1_percent=100.0 * f1,
            semantic_exact_match=sem,
            semantic_exact_match_percent=100.0 * sem,
        )
        empty_answers = [row for row in records if not str(row.get("answer") or "").strip()]
        categories: dict[str, int] = {}
        for row in records:
            category = row.get("error_category")
            if category:
                categories[category] = categories.get(category, 0) + 1
        retrieval_means = {}
        for key in ("gold_row_recall", "gold_hyperlink_recall", "gold_passage_recall"):
            values = [row.get("retrieval_audit", {}).get(key) for row in records if isinstance(row.get("retrieval_audit"), dict)]
            values = [float(v) for v in values if v is not None]
            retrieval_means[f"mean_{key}"] = sum(values) / len(values) if values else None

        audit_sample = [
            {key: row.get(key) for key in ("id", "question", "gold_answer", "answer", "error_category", "retrieval_audit")}
            for row in records if row.get("error_category")
        ][:100]

        ambiguous_rows = [r for r in records if r.get("is_ambiguous") is True]
        unambiguous_rows = [r for r in records if r.get("is_ambiguous") is False]
        ambiguity_metrics = {}
        if ambiguous_rows:
            ambiguity_metrics.update(
                ambiguous_count=len(ambiguous_rows),
                ambiguous_exact_match=sum(r.get("exact_match") or 0.0 for r in ambiguous_rows) / len(ambiguous_rows),
                ambiguous_semantic_exact_match=sum(r.get("semantic_exact_match") or 0.0 for r in ambiguous_rows) / len(ambiguous_rows),
                ambiguous_f1=sum(r.get("f1") or 0.0 for r in ambiguous_rows) / len(ambiguous_rows),
            )
        if unambiguous_rows:
            ambiguity_metrics.update(
                unambiguous_count=len(unambiguous_rows),
                unambiguous_exact_match=sum(r.get("exact_match") or 0.0 for r in unambiguous_rows) / len(unambiguous_rows),
                unambiguous_semantic_exact_match=sum(r.get("semantic_exact_match") or 0.0 for r in unambiguous_rows) / len(unambiguous_rows),
                unambiguous_f1=sum(r.get("f1") or 0.0 for r in unambiguous_rows) / len(unambiguous_rows),
            )
        summary.update(
            empty_answer_count=len(empty_answers),
            empty_answer_rate=(len(empty_answers) / len(records) if records else 0.0),
            error_taxonomy=categories,
            error_audit_sample=audit_sample,
            **ambiguity_metrics,
            **retrieval_means,
        )
    elif args.dataset == "finqa":
        execution = (
            sum(row.get("execution_accuracy") or 0.0 for row in records) / len(records)
            if records else 0.0
        )
        official_execution = (
            sum(row.get("official_execution_accuracy") or 0.0 for row in records) / len(records)
            if records else 0.0
        )
        summary.update(
            execution_accuracy=execution,
            execution_accuracy_percent=100.0 * execution,
            official_execution_accuracy=official_execution,
            official_execution_accuracy_percent=100.0 * official_execution,
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
            categories = {}
            for row in records:
                cat = row.get("error_category")
                if cat:
                    categories[cat] = categories.get(cat, 0) + 1
            summary["error_taxonomy"] = categories
    else:
        accuracy = (
            sum(row.get("denotation_accuracy") or 0.0 for row in records) / len(records)
            if records else 0.0
        )
        summary.update(
            denotation_accuracy=accuracy,
            denotation_accuracy_percent=100.0 * accuracy,
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
        "top_k": getattr(args, "top_k", None),
        "use_rule_text_triples": getattr(args, "use_rule_text_triples", None),
        "use_record_nodes": getattr(args, "use_record_nodes", None),
        "use_path_guidance": getattr(args, "use_path_guidance", None),
        "use_lexical_tiebreak": getattr(args, "use_lexical_tiebreak", None),
        "use_hyperlink_expansion": getattr(args, "use_hyperlink_expansion", None),
        "use_collision_evidence_expansion": getattr(args, "use_collision_evidence_expansion", None),
        "collision_passage_budget": getattr(args, "collision_passage_budget", None),
        "use_focus_evidence_augmentation": getattr(args, "use_focus_evidence_augmentation", None),
        "focus_passage_budget_per_candidate": getattr(args, "focus_passage_budget_per_candidate", None),
        "use_diagnostic_focus_resolution": getattr(args, "use_diagnostic_focus_resolution", None),
        "focus_query_fallback_budget": getattr(args, "focus_query_fallback_budget", None),
        "l2_existing_witness_budget": getattr(args, "l2_existing_witness_budget", None),
        "l2_max_edges_per_candidate": getattr(args, "l2_max_edges_per_candidate", None),
        "l2_max_contexts_per_candidate": getattr(args, "l2_max_contexts_per_candidate", None),
        "l2_context_snippet_chars": getattr(args, "l2_context_snippet_chars", None),
        "use_adaptive_verification": getattr(args, "use_adaptive_verification", None),
        "l2_evidence_mode": getattr(args, "l2_evidence_mode", None),
        "use_prompt_compression": getattr(args, "use_prompt_compression", None),
        "use_path_focused_prompt": getattr(args, "use_path_focused_prompt", None),
        "prompt_path_budget": getattr(args, "prompt_path_budget", None),
        "ambiguity_policy": getattr(args, "ambiguity_policy", None),
        "oueg_context_mode": getattr(args, "oueg_context_mode", None),
        "max_context_chars": getattr(args, "max_context_chars", None),
        "max_output_tokens": getattr(args, "max_output_tokens", None),
        "temperature": getattr(args, "temperature", None),
        "n_paths": getattr(args, "n_paths", None),
        "strict_path_text_top_n": getattr(args, "strict_path_text_top_n", None),
        "max_replans": getattr(args, "max_replans", None),
        "max_table_rows_for_kg": getattr(args, "max_table_rows_for_kg", None),
        "finqa_table_format": getattr(args, "finqa_table_format", None),
        "second_stage_k": getattr(args, "second_stage_k", None),
        "write_completion_order": getattr(args, "write_completion_order", False),
        "max_workers": max_workers,
        "llm_max_concurrent_requests": int(
            os.environ.get(
                f"{os.environ.get('LLM_PROVIDER', '').strip().upper()}_MAX_CONCURRENT_REQUESTS",
                os.environ.get("LLM_MAX_CONCURRENT_REQUESTS", "8"),
            )
        ),
    }
    return summary


class AsyncBenchmarkLogger:
    """Dedicated background logging thread for benchmarks.
    
    Responsibilities:
    - Decouples disk I/O and JSON serialization from the LLM worker threads.
    - Preserves deterministic record ordering if write_completion_order=False.
    - Flushes every record to disk immediately so partial progress is never lost.
    - Periodically writes atomic .summary.json updates during execution.
    - Computes final benchmark metrics in milliseconds without reading multi-MB files from disk.
    """

    def __init__(
        self,
        output_path: Path,
        total_pending: int,
        args: argparse.Namespace,
        run_manifest: dict[str, Any],
        manifest_path: Path,
        max_workers: int,
        initial_records: list[dict[str, Any]] | None = None,
    ):
        self.output_path = output_path
        self.summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
        self.args = args
        self.run_manifest = run_manifest
        self.manifest_path = manifest_path
        self.max_workers = max_workers
        self.write_completion_order = getattr(args, "write_completion_order", False)
        
        self.mode = "a" if (args.resume and output_path.exists()) else "w"
        self.queue: queue.Queue[tuple[int, dict[str, Any]] | None] = queue.Queue(maxsize=256)
        
        # In-memory lightweight projection of completed records
        self.lightweight_records: list[dict[str, Any]] = [
            extract_summary_record(r) for r in (initial_records or [])
        ]
        
        # Sequence buffering for deterministic record ordering
        self.pending_seq_buffer: dict[int, dict[str, Any]] = {}
        self.next_seq_idx: int = 0
        
        # Running metrics for live progress bar
        self.done_count = 0
        self.em_acc = 0.0
        self.calls_acc = 0.0
        self.last_summary_write_time = time.time()
        
        # Progress bar setup
        disable_progress = args.no_progress or (not args.force_progress and not sys.stderr.isatty())
        self.progress = None
        if not disable_progress:
            self.progress = tqdm(
                total=total_pending,
                desc=f"{args.dataset}/{args.method}",
                unit="sample",
                dynamic_ncols=True,
            )

        # Start background writer thread
        self.writer_thread = threading.Thread(
            target=self._writer_loop,
            name="AsyncBenchmarkLoggerThread",
            daemon=True,
        )
        self.writer_thread.start()

    def log_record(self, seq_idx: int, record: dict[str, Any]) -> None:
        """Enqueue finished record. Called immediately by worker threads (non-blocking)."""
        self.queue.put((seq_idx, record))

    def _write_one(self, file_handle, record: dict[str, Any]) -> None:
        """Write single record to JSONL, flush, update stats and progress."""
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        file_handle.write(line)
        file_handle.flush()

        if not getattr(self.args, "quiet_records", False):
            print(line, end="")

        self.lightweight_records.append(extract_summary_record(record))
        self.done_count += 1
        
        em_val = float(record.get("exact_match") or 0.0)
        calls_val = float(record.get("llm_calls") or 0.0)
        self.em_acc += em_val
        self.calls_acc += calls_val

        if self.progress is not None:
            self.progress.set_postfix(
                em=f"{100.0 * self.em_acc / self.done_count:.1f}%",
                avg_calls=f"{self.calls_acc / self.done_count:.1f}",
                refresh=False,
            )
            self.progress.update(1)

        # Periodically atomic-update .summary.json so monitor tools see real-time progress
        now = time.time()
        if (now - self.last_summary_write_time >= 4.0) or (self.done_count % 5 == 0):
            self._write_running_summary()
            self.last_summary_write_time = now

    def _write_running_summary(self) -> None:
        """Write atomic running summary to disk without blocking workers."""
        try:
            summary = compute_benchmark_summary(
                self.lightweight_records,
                self.args,
                self.run_manifest,
                self.manifest_path,
                self.max_workers,
            )
            tmp_path = self.summary_path.with_suffix(self.summary_path.suffix + ".tmp")
            tmp_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp_path.replace(self.summary_path)
        except Exception:
            pass  # Best effort during intermediate streaming

    def _writer_loop(self) -> None:
        """Dedicated writer loop running on background thread."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open(self.mode, encoding="utf-8") as out_file:
            while True:
                item = self.queue.get()
                if item is None:  # Sentinel to terminate
                    self.queue.task_done()
                    break

                seq_idx, record = item
                if self.write_completion_order:
                    self._write_one(out_file, record)
                else:
                    self.pending_seq_buffer[seq_idx] = record
                    while self.next_seq_idx in self.pending_seq_buffer:
                        ready_record = self.pending_seq_buffer.pop(self.next_seq_idx)
                        self._write_one(out_file, ready_record)
                        self.next_seq_idx += 1

                self.queue.task_done()

            # Flush any remaining out-of-order buffer (e.g. if interrupted or partial)
            if self.pending_seq_buffer:
                for idx in sorted(self.pending_seq_buffer):
                    self._write_one(out_file, self.pending_seq_buffer[idx])
                self.pending_seq_buffer.clear()

    def close(self) -> dict[str, Any]:
        """Signal writer thread to finish, wait for completion, save final summary."""
        self.queue.put(None)
        self.writer_thread.join()

        if self.progress is not None:
            self.progress.close()

        # Compute final complete summary
        summary = compute_benchmark_summary(
            self.lightweight_records,
            self.args,
            self.run_manifest,
            self.manifest_path,
            self.max_workers,
        )
        self.summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
        return summary
