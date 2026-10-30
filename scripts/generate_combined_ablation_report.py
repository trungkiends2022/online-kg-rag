#!/usr/bin/env python3
"""Compute fast individual and pooled (Shard 01 + Shard 02) ablation benchmark summary."""

import json
from pathlib import Path

CONFIGS = [
    ("full", "Full OUEG Control"),
    ("no_record_nodes", "No Record Nodes (-Centroids)"),
    ("no_path_guidance", "No Path Guidance"),
    ("l1_only", "L1 Only (No L2 Verification)"),
    ("no_l2_new_evidence", "No L2 New Evidence"),
    ("no_diagnostic_focus_resolution", "No Diagnostic Focus Resolution"),
    ("no_prompt_compression", "No Prompt Compression"),
]

def load_summary(summary_path: Path):
    if not summary_path.exists():
        return None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        n = data.get("num_examples", 0)
        if n == 0:
            return None
        em = data.get("exact_match_percent", data.get("exact_match", 0) * 100)
        sem = data.get("semantic_exact_match_percent", data.get("semantic_exact_match", 0) * 100)
        f1 = data.get("f1_percent", data.get("f1", 0) * 100)
        empty_count = data.get("empty_answer_count", 0)
        empty_pct = data.get("empty_answer_rate", empty_count / n) * 100
        calls = data.get("mean_llm_calls", data.get("total_llm_calls", n) / n)
        
        return {
            "n": n,
            "em": em,
            "em_count": round(em * n / 100),
            "sem": sem,
            "sem_count": round(sem * n / 100),
            "f1": f1,
            "f1_sum": f1 * n / 100,
            "empty_count": empty_count,
            "empty_pct": empty_pct,
            "calls": calls,
            "calls_sum": calls * n,
        }
    except Exception:
        return None

def main():
    root = Path(__file__).resolve().parent.parent
    dir_s1 = root / "data/results/hybridqa-shard01-ablations-120b"
    dir_s2 = root / "data/results/hybridqa-shard02-ablations-120b"
    report_file = root / "reports/ablation_study_shard01_shard02_gpt_oss_120b.md"
    
    results = {}
    for cfg, label in CONFIGS:
        p1 = list((dir_s1 / cfg).glob("*.summary.json"))
        p2 = list((dir_s2 / cfg).glob("*.summary.json"))
        m1 = load_summary(p1[0]) if p1 else None
        m2 = load_summary(p2[0]) if p2 else None
        
        # Pooled
        pooled = None
        if m1 and m2:
            tot_n = m1["n"] + m2["n"]
            tot_em = m1["em_count"] + m2["em_count"]
            tot_sem = m1["sem_count"] + m2["sem_count"]
            tot_empty = m1["empty_count"] + m2["empty_count"]
            mean_f1 = (m1["f1_sum"] + m2["f1_sum"]) / tot_n * 100
            mean_calls = (m1["calls_sum"] + m2["calls_sum"]) / tot_n
            
            pooled = {
                "n": tot_n,
                "em": tot_em / tot_n * 100,
                "sem": tot_sem / tot_n * 100,
                "f1": mean_f1,
                "empty_count": tot_empty,
                "empty_pct": tot_empty / tot_n * 100,
                "calls": mean_calls
            }
        results[cfg] = {"label": label, "s1": m1, "s2": m2, "pooled": pooled}
        
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
