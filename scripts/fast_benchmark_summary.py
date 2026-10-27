#!/usr/bin/env python3
"""
Ultra-fast benchmark summary & comparison tool for Online KG RAG / HybridQA / OTT-QA / FinQA.

Usage:
  # Summarize a single file:
  python scripts/fast_benchmark_summary.py data/results/hybridqa-1500-seed2027/oueg-focus-recovery-shard02-30.jsonl

  # Compare multiple benchmark files side-by-side:
  python scripts/fast_benchmark_summary.py \
    data/results/hybridqa-1500-seed2027/oueg-focus-recovery-shard02-30.jsonl \
    data/results/hybridqa-1500-seed2027/direct_llm-shard02-30.jsonl \
    data/results/hybridqa-1500-seed2027/odyssey-shard02-30.jsonl

  # Summarize all results in a directory:
  python scripts/fast_benchmark_summary.py data/results/ottqa-500-seed2027/

  # Head-to-head detailed comparison between two runs:
  python scripts/fast_benchmark_summary.py --compare \
    data/results/hybridqa-1500-seed2027/oueg-focus-recovery-shard02-30.jsonl \
    data/results/hybridqa-1500-seed2027/direct_llm-shard02-30.jsonl
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def load_file_fast(path_str: str, need_records: bool = False) -> dict[str, Any]:
    """Load benchmark data ultra-fast: prefer .summary.json if available, or stream parse jsonl."""
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    # Check for precomputed summary
    summary_path = Path(f"{path}.summary.json") if not path.name.endswith(".summary.json") else path
    has_summary = summary_path.is_file()

    summary_data = None
    if has_summary:
        try:
            summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            summary_data = None

    # Ultra-fast path: If precomputed summary exists and detailed case records are not needed
    if summary_data and not need_records:
        return {
            "path": str(path),
            "label": path.name.replace(".jsonl", "").replace(".summary.json", ""),
            "summary": summary_data,
            "records": {},
        }

    # Stream parse jsonl records with minimal projection to avoid storing multi-MB KG payloads
    records: dict[str, dict[str, Any]] = {}
    jsonl_path = path if path.suffix == ".jsonl" else Path(str(path).replace(".summary.json", ""))
    
    if jsonl_path.is_file():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    qid = str(d.get("id") or d.get("question_id") or "")
                    if not qid:
                        continue
                    ans = str(d.get("answer") or "").strip()
                    gold = str(d.get("gold_answer") or d.get("answer_text") or "").strip()
                    em = float(d.get("exact_match") or 0.0)
                    sem = float(d.get("semantic_exact_match") or em)
                    f1 = float(d.get("f1") or 0.0)
                    is_amb = d.get("is_ambiguous") is True or (
                        isinstance(d.get("ambiguity"), dict) and d["ambiguity"].get("is_ambiguous") is True
                    )
                    latency = float(d.get("wall_time_ms") or d.get("latency_ms") or 0.0)
                    calls = int(d.get("llm_calls") or (1 if d.get("llm_latency_ms") else 0))
                    
                    records[qid] = {
                        "id": qid,
                        "question": str(d.get("question") or ""),
                        "gold": gold,
                        "answer": ans,
                        "is_empty": (ans == ""),
                        "exact_match": em,
                        "semantic_exact_match": sem,
                        "f1": f1,
                        "is_ambiguous": is_amb,
                        "wall_time_ms": latency,
                        "llm_calls": calls,
                        "error_category": d.get("error_category"),
                    }
                except Exception:
                    continue

    # Fallback to compute summary from records if summary_data was missing
    if not summary_data and records:
        n = len(records)
        em_avg = sum(r["exact_match"] for r in records.values()) / n if n else 0.0
        f1_avg = sum(r["f1"] for r in records.values()) / n if n else 0.0
        sem_avg = sum(r["semantic_exact_match"] for r in records.values()) / n if n else 0.0
        empty_cnt = sum(1 for r in records.values() if r["is_empty"])
        
        amb_rows = [r for r in records.values() if r["is_ambiguous"]]
        unamb_rows = [r for r in records.values() if not r["is_ambiguous"]]
        
        summary_data = {
            "method": jsonl_path.stem.split("-")[0],
            "dataset": "unknown",
            "num_examples": n,
            "exact_match_percent": em_avg * 100,
            "f1_percent": f1_avg * 100,
            "semantic_exact_match_percent": sem_avg * 100,
            "empty_answer_count": empty_cnt,
            "empty_answer_rate": empty_cnt / n if n else 0.0,
            "ambiguous_count": len(amb_rows),
            "ambiguous_exact_match": (sum(r["exact_match"] for r in amb_rows) / len(amb_rows)) if amb_rows else 0.0,
            "unambiguous_count": len(unamb_rows),
            "unambiguous_exact_match": (sum(r["exact_match"] for r in unamb_rows) / len(unamb_rows)) if unamb_rows else 0.0,
            "mean_wall_time_ms": sum(r["wall_time_ms"] for r in records.values()) / n if n else 0.0,
            "mean_llm_calls": sum(r["llm_calls"] for r in records.values()) / n if n else 1.0,
        }

    label = jsonl_path.stem if jsonl_path.is_file() else path.stem
    return {
        "path": str(jsonl_path if jsonl_path.is_file() else path),
        "label": label,
        "summary": summary_data or {},
        "records": records,
    }


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format standard markdown table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(val)))
    
    header_str = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    sep_str = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    row_strs = ["| " + " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)) + " |" for row in rows]
    return "\n".join([header_str, sep_str] + row_strs)


def display_comparison(results: list[dict[str, Any]]) -> str:
    """Produce clean, comprehensive comparative markdown report."""
    headers = ["Metric"] + [r["label"] for r in results]
    
    def get_val(r, key, fmt=None, default="N/A"):
        s = r.get("summary", {})
        if key not in s:
            return default
        v = s[key]
        if fmt:
            return fmt(v)
        return str(v)

    rows = [
        ["Total Examples"] + [str(get_val(r, "num_examples", int, 0)) for r in results],
        ["Exact Match (EM)"] + [f"{get_val(r, 'exact_match_percent', lambda x: f'{float(x):.2f}%')}" for r in results],
        ["Token F1"] + [f"{get_val(r, 'f1_percent', lambda x: f'{float(x):.2f}%')}" for r in results],
        ["Semantic EM"] + [f"{get_val(r, 'semantic_exact_match_percent', lambda x: f'{float(x):.2f}%')}" for r in results],
        ["Empty Answers"] + [f"{get_val(r, 'empty_answer_count')} ({get_val(r, 'empty_answer_rate', lambda x: f'{float(x)*100:.1f}%')})" for r in results],
        ["Unambiguous EM"] + [f"{get_val(r, 'unambiguous_exact_match', lambda x: f'{float(x)*100:.2f}%')}" for r in results],
        ["Ambiguous EM"] + [f"{get_val(r, 'ambiguous_exact_match', lambda x: f'{float(x)*100:.2f}%')}" for r in results],
        ["Mean Latency (s)"] + [f"{get_val(r, 'mean_wall_time_ms', lambda x: f'{float(x)/1000:.2f}s')}" for r in results],
        ["Mean LLM Calls"] + [f"{get_val(r, 'mean_llm_calls', lambda x: f'{float(x):.2f}')}" for r in results],
    ]
    
    table = format_table(headers, rows)
    out = [f"### 📊 Benchmark Summary ({len(results)} runs compared)\n", table]
    return "\n".join(out)


def display_head_to_head(run_a: dict[str, Any], run_b: dict[str, Any]) -> str:
    """Detailed win/loss/tie diagnostic between two runs."""
    rec_a = run_a["records"]
    rec_b = run_b["records"]
    common_ids = [qid for qid in rec_a if qid in rec_b]
    
    if not common_ids:
        return "No common question IDs found between the two runs."
    
    a_wins = []
    b_wins = []
    both_correct = []
    both_wrong = []
    
    for qid in common_ids:
        item_a = rec_a[qid]
        item_b = rec_b[qid]
        em_a = item_a["exact_match"]
        em_b = item_b["exact_match"]
        
        if em_a > em_b:
            a_wins.append((qid, item_a, item_b))
        elif em_b > em_a:
            b_wins.append((qid, item_a, item_b))
        elif em_a == 1.0 and em_b == 1.0:
            both_correct.append((qid, item_a, item_b))
        else:
            both_wrong.append((qid, item_a, item_b))
            
    total = len(common_ids)
    name_a = run_a["label"]
    name_b = run_b["label"]
    
    lines = [
        f"\n### 🥊 Head-to-Head: `{name_a}` vs `{name_b}` (N={total})",
        f"- **{name_a} Thắng**: {len(a_wins)} ({len(a_wins)/total*100:.1f}%)",
        f"- **{name_b} Thắng**: {len(b_wins)} ({len(b_wins)/total*100:.1f}%)",
        f"- **Cả hai cùng đúng**: {len(both_correct)} ({len(both_correct)/total*100:.1f}%)",
        f"- **Cả hai cùng sai**: {len(both_wrong)} ({len(both_wrong)/total*100:.1f}%)",
    ]
    
    if a_wins:
        lines.append(f"\n#### Các case `{name_a}` thắng `{name_b}`:")
        rows = [["ID", "Gold Answer", f"{name_a} (Win)", f"{name_b} (Loss)"]]
        for qid, ia, ib in a_wins[:10]:
            rows.append([qid, ia["gold"], ia["answer"] or "(Empty)", ib["answer"] or "(Empty)"])
        lines.append(format_table(rows[0], rows[1:]))
        
    if b_wins:
        lines.append(f"\n#### Các case `{name_b}` thắng `{name_a}`:")
        rows = [["ID", "Gold Answer", f"{name_a} (Loss)", f"{name_b} (Win)"]]
        for qid, ia, ib in b_wins[:10]:
            rows.append([qid, ia["gold"], ia["answer"] or "(Empty)", ib["answer"] or "(Empty)"])
        lines.append(format_table(rows[0], rows[1:]))

    return "\n".join(lines)


def collect_target_files(inputs: list[str]) -> list[str]:
    """Recursively collect valid benchmark jsonl or summary files from inputs."""
    target_files = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            # Recursive search for .jsonl files, skipping logs directories
            found = sorted(glob.glob(os.path.join(inp, "**", "*.jsonl"), recursive=True))
            if not found:
                # Try finding .summary.json
                found = sorted(glob.glob(os.path.join(inp, "**", "*.summary.json"), recursive=True))
            valid = [
                f for f in found
                if not f.endswith(".manifest.json") and "/logs/" not in f and not f.endswith(".log")
            ]
            target_files.extend(valid)
        elif p.is_file():
            target_files.append(str(p))
        else:
            matched = sorted(glob.glob(inp, recursive=True))
            if matched:
                target_files.extend([m for m in matched if not m.endswith(".manifest.json") and "/logs/" not in m])
            else:
                print(f"Warning: path not found: {inp}", file=sys.stderr)

    # Dedup while preserving order
    seen = set()
    deduped = []
    for f in target_files:
        base = f.replace(".summary.json", "")
        if base not in seen:
            seen.add(base)
            deduped.append(f)
    return deduped


CANONICAL_ORDER = [
    # Baselines
    "online_unified_evidence_graph",
    "direct_llm",
    "odyssey",
    "graph_retrieval_no_path",
    "path_text_top_n",
    "flat_rag_shared_context",
    "oracle_kg_retrieval",
    # Ablations
    "full",
    "no_record_nodes",
    "no_path_guidance",
    "l1_only",
    "no_l2_new_evidence",
    "no_diagnostic_focus_resolution",
    "no_prompt_compression",
    "no_hyperlink_expansion",
]


def extract_group_key(path_str: str) -> str:
    """Determine group/method/ablation key for shard aggregation."""
    p = Path(path_str)
    parent_name = p.parent.name
    if parent_name in CANONICAL_ORDER:
        return parent_name
    
    stem = p.name.replace(".jsonl", "").replace(".summary.json", "")
    parts = stem.split("__")
    if len(parts) >= 2:
        last = parts[-1]
        if last in CANONICAL_ORDER:
            return last
        # Check method part
        for part in reversed(parts):
            if part in CANONICAL_ORDER:
                return part
    return parent_name if parent_name not in ("", ".", "results") else stem


def aggregate_group(group_label: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate multiple shard summaries belonging to the same configuration."""
    if len(items) == 1:
        item = items[0].copy()
        item["label"] = group_label
        return item

    total_n = sum(item["summary"].get("num_examples", 0) for item in items)
    if total_n == 0:
        return {"label": group_label, "summary": {}, "records": {}, "path": items[0]["path"]}

    em_acc = sum(item["summary"].get("exact_match_percent", 0.0) * item["summary"].get("num_examples", 0) for item in items)
    f1_acc = sum(item["summary"].get("f1_percent", 0.0) * item["summary"].get("num_examples", 0) for item in items)
    sem_acc = sum(item["summary"].get("semantic_exact_match_percent", 0.0) * item["summary"].get("num_examples", 0) for item in items)
    empty_cnt = sum(item["summary"].get("empty_answer_count", 0) for item in items)
    
    wall_time = sum(item["summary"].get("mean_wall_time_ms", 0.0) * item["summary"].get("num_examples", 0) for item in items)
    llm_calls = sum(item["summary"].get("mean_llm_calls", 0.0) * item["summary"].get("num_examples", 0) for item in items)

    unamb_cnt = sum(item["summary"].get("unambiguous_count", 0) for item in items)
    amb_cnt = sum(item["summary"].get("ambiguous_count", 0) for item in items)
    unamb_em = sum(item["summary"].get("unambiguous_exact_match", 0.0) * item["summary"].get("unambiguous_count", 0) for item in items) / unamb_cnt if unamb_cnt else None
    amb_em = sum(item["summary"].get("ambiguous_exact_match", 0.0) * item["summary"].get("ambiguous_count", 0) for item in items) / amb_cnt if amb_cnt else None

    agg_summary = {
        "num_examples": total_n,
        "exact_match_percent": em_acc / total_n,
        "f1_percent": f1_acc / total_n,
        "semantic_exact_match_percent": sem_acc / total_n,
        "empty_answer_count": empty_cnt,
        "empty_answer_rate": empty_cnt / total_n,
        "mean_wall_time_ms": wall_time / total_n,
        "mean_llm_calls": llm_calls / total_n,
    }
    if unamb_em is not None:
        agg_summary["unambiguous_exact_match"] = unamb_em
    if amb_em is not None:
        agg_summary["ambiguous_exact_match"] = amb_em

    merged_records = {}
    for it in items:
        merged_records.update(it.get("records", {}))

    return {
        "label": f"{group_label} ({len(items)} shards)",
        "summary": agg_summary,
        "records": merged_records,
        "path": items[0]["path"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+", help="JSONL file(s), summary JSON(s), or directories containing results")
    parser.add_argument("--compare", action="store_true", help="Perform head-to-head per-sample win/loss comparison")
    parser.add_argument("--no-aggregate", action="store_true", help="Do not aggregate shards; show each file separately")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON format")
    args = parser.parse_args()

    target_files = collect_target_files(args.inputs)

    if not target_files:
        print("No valid benchmark result files found.", file=sys.stderr)
        sys.exit(1)

    need_records = bool(args.compare)
    start_time = time.perf_counter()
    raw_results = [load_file_fast(f, need_records=need_records) for f in target_files]

    if not args.no_aggregate and len(raw_results) > 1:
        # Group by configuration
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in raw_results:
            key = extract_group_key(r["path"])
            groups.setdefault(key, []).append(r)

        # Sort groups canonically if possible
        def sort_key(k: str) -> tuple[int, str]:
            base = k.split(" ")[0]
            if base in CANONICAL_ORDER:
                return (CANONICAL_ORDER.index(base), base)
            return (999, k)

        sorted_keys = sorted(groups.keys(), key=sort_key)
        results = [aggregate_group(k, groups[k]) for k in sorted_keys]
    else:
        results = raw_results

    load_duration = (time.perf_counter() - start_time) * 1000

    if args.json:
        out_json = {r["label"]: r["summary"] for r in results}
        print(json.dumps(out_json, indent=2, ensure_ascii=False))
        return

    # Print general comparison
    md_output = display_comparison(results)
    print(md_output)

    # If head-to-head requested
    if args.compare and len(results) >= 2:
        h2h_output = display_head_to_head(results[0], results[1])
        print(h2h_output)
        md_output += "\n\n" + h2h_output

    # Automatically save benchmark_summary.md and benchmark_summary.json if input contains a directory
    first_input = Path(args.inputs[0])
    target_dir = first_input if first_input.is_dir() else (first_input.parent if len(args.inputs) == 1 else None)
    if target_dir and target_dir.is_dir():
        try:
            summary_md_path = target_dir / "benchmark_summary.md"
            summary_json_path = target_dir / "benchmark_summary.json"
            summary_md_path.write_text(md_output + "\n", encoding="utf-8")
            out_json = {r["label"]: r["summary"] for r in results}
            summary_json_path.write_text(json.dumps(out_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"💾 *Đã lưu bảng tổng hợp tại:* `{summary_md_path}`")
        except Exception as e:
            print(f"Warning: could not save summary file: {e}", file=sys.stderr)

    print(f"\n⚡ *Tổng hợp xong {len(results)} cấu hình ({len(target_files)} files) trong {load_duration:.1f}ms.*")


if __name__ == "__main__":
    main()
