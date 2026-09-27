#!/usr/bin/env python3
"""Compare OUEG vs Direct LLM across benchmark runs with ambiguity stratification."""

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oueg", type=Path, required=True, help="OUEG results JSONL")
    parser.add_argument("--direct", type=Path, required=True, help="Direct LLM results JSONL")
    parser.add_argument("--markdown", type=Path, help="Optional output markdown report path")
    return parser.parse_args()


def load_jsonl(path: Path) -> dict[str, dict]:
    records = {}
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        records[row["id"]] = row
    return records


def compute_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {
            "count": 0,
            "em": 0.0,
            "sem_em": 0.0,
            "f1": 0.0,
            "empty_rate": 0.0,
            "avg_latency": 0.0,
        }
    n = len(rows)
    em = sum(r.get("exact_match", 0.0) for r in rows) / n
    sem = sum(r.get("semantic_exact_match", 0.0) for r in rows) / n
    f1 = sum(r.get("f1", 0.0) for r in rows) / n
    empty = sum(not str(r.get("answer") or "").strip() for r in rows) / n
    latency = sum(r.get("wall_time_ms", 0.0) for r in rows) / n
    return {
        "count": n,
        "em": em * 100,
        "sem_em": sem * 100,
        "f1": f1 * 100,
        "empty_rate": empty * 100,
        "avg_latency": latency / 1000.0,
    }


def main():
    args = parse_args()
    oueg_map = load_jsonl(args.oueg)
    direct_map = load_jsonl(args.direct)

    common_ids = [k for k in oueg_map if k in direct_map]
    print(f"Loaded {len(oueg_map)} OUEG, {len(direct_map)} Direct LLM, {len(common_ids)} common.")

    oueg_rows = [oueg_map[i] for i in common_ids]
    direct_rows = [direct_map[i] for i in common_ids]

    # Ambiguity is determined from OUEG's structural candidate analysis
    ambiguous_ids = set()
    for row in oueg_rows:
        if row.get("is_ambiguous") is True:
            ambiguous_ids.add(row["id"])
        elif isinstance(row.get("ambiguity"), dict) and row["ambiguity"].get("is_ambiguous"):
            ambiguous_ids.add(row["id"])

    # Stratified subsets
    oueg_amb = [r for r in oueg_rows if r["id"] in ambiguous_ids]
    oueg_unamb = [r for r in oueg_rows if r["id"] not in ambiguous_ids]

    direct_amb = [r for r in direct_rows if r["id"] in ambiguous_ids]
    direct_unamb = [r for r in direct_rows if r["id"] not in ambiguous_ids]

    m_oueg_all = compute_metrics(oueg_rows)
    m_dir_all = compute_metrics(direct_rows)

    m_oueg_unamb = compute_metrics(oueg_unamb)
    m_dir_unamb = compute_metrics(direct_unamb)

    m_oueg_amb = compute_metrics(oueg_amb)
    m_dir_amb = compute_metrics(direct_amb)

    report_lines = []
    report_lines.append(f"# Benchmark Comparison: OUEG vs Direct LLM (N={len(common_ids)})")
    report_lines.append("")
    report_lines.append(f"- **Total Evaluated Cases**: {len(common_ids)}")
    report_lines.append(f"- **Ambiguous Cases (Multiple structural ties/candidates)**: {len(ambiguous_ids)} ({len(ambiguous_ids)/len(common_ids)*100:.1f}%)")
    report_lines.append(f"- **Unambiguous Cases**: {len(common_ids) - len(ambiguous_ids)} ({(len(common_ids) - len(ambiguous_ids))/len(common_ids)*100:.1f}%)")
    report_lines.append("")
    report_lines.append("## Overall Performance")
    report_lines.append("")
    report_lines.append("| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |")
    report_lines.append("|---|---|---|---|")
    report_lines.append(f"| **Exact Match (EM)** | {m_dir_all['em']:.2f}% | {m_oueg_all['em']:.2f}% | {m_oueg_all['em'] - m_dir_all['em']:+.2f}% |")
    report_lines.append(f"| **Semantic EM** | {m_dir_all['sem_em']:.2f}% | {m_oueg_all['sem_em']:.2f}% | {m_oueg_all['sem_em'] - m_dir_all['sem_em']:+.2f}% |")
    report_lines.append(f"| **Token F1** | {m_dir_all['f1']:.2f}% | {m_oueg_all['f1']:.2f}% | {m_oueg_all['f1'] - m_dir_all['f1']:+.2f}% |")
    report_lines.append(f"| **Empty Answer Rate** | {m_dir_all['empty_rate']:.2f}% | {m_oueg_all['empty_rate']:.2f}% | {m_oueg_all['empty_rate'] - m_dir_all['empty_rate']:+.2f}% |")
    report_lines.append(f"| **Avg Latency (sec)** | {m_dir_all['avg_latency']:.2f}s | {m_oueg_all['avg_latency']:.2f}s | {m_oueg_all['avg_latency'] - m_dir_all['avg_latency']:+.2f}s |")
    report_lines.append("")
    report_lines.append("## Ambiguity Breakdown")
    report_lines.append("")
    report_lines.append("| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |")
    report_lines.append("|---|---|---|---|---|---|")
    report_lines.append(f"| **Unambiguous Cases** | {m_oueg_unamb['count']} | {m_dir_unamb['em']:.2f}% | {m_oueg_unamb['em']:.2f}% | {m_dir_unamb['f1']:.2f}% | {m_oueg_unamb['f1']:.2f}% |")
    report_lines.append(f"| **Ambiguous Cases** | {m_oueg_amb['count']} | {m_dir_amb['em']:.2f}% | {m_oueg_amb['em']:.2f}% | {m_dir_amb['f1']:.2f}% | {m_oueg_amb['f1']:.2f}% |")
    report_lines.append("")

    if ambiguous_ids:
        report_lines.append("## Case Inspection: Ambiguous Samples")
        report_lines.append("")
        report_lines.append("| ID | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |")
        report_lines.append("|---|---|---|---|---|---|")
        for ex_id in ambiguous_ids:
            o_row = oueg_map[ex_id]
            d_row = direct_map[ex_id]
            amb_info = o_row.get("ambiguity") or {}
            status = amb_info.get("status", "AMBIGUOUS")
            q = o_row["question"]
            gold = o_row["gold_answer"]
            d_ans = d_row.get("answer", "")
            o_ans = o_row.get("answer", "")
            report_lines.append(f"| `{ex_id}` | {q} | **{gold}** | {d_ans} | {o_ans} | {status} |")
        report_lines.append("")

    report_text = "\n".join(report_lines)
    print(report_text)

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(report_text, encoding="utf-8")
        print(f"Saved comparison report to {args.markdown}")


if __name__ == "__main__":
    main()
