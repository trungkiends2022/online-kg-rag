#!/usr/bin/env python3
"""Report paired QEG metrics separately for predefined HybridQA strata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        identifier = str(row["id"])
        if identifier in rows:
            raise ValueError(f"duplicate id {identifier!r} in {path}")
        rows[identifier] = row
    return rows


def _summary(qeg: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]], ids: list[str]) -> dict:
    missing_qeg = set(ids) - set(qeg)
    missing_baseline = set(ids) - set(baseline)
    if missing_qeg or missing_baseline:
        raise ValueError(
            f"missing in qeg={sorted(missing_qeg)}; "
            f"missing in baseline={sorted(missing_baseline)}",
        )
    qeg_rows = [qeg[identifier] for identifier in ids]
    baseline_rows = [baseline[identifier] for identifier in ids]
    qeg_only = baseline_only = both_correct = both_wrong = 0
    for candidate, control in zip(qeg_rows, baseline_rows):
        candidate_correct, control_correct = bool(candidate.get("exact_match")), bool(control.get("exact_match"))
        if candidate_correct and not control_correct:
            qeg_only += 1
        elif control_correct and not candidate_correct:
            baseline_only += 1
        elif candidate_correct:
            both_correct += 1
        else:
            both_wrong += 1
    average = lambda rows, key: round(sum(float(row.get(key) or 0.0) for row in rows) / len(rows), 6)
    grounded = sum(row.get("answer_evidence_verified") is True for row in qeg_rows)
    return {
        "n": len(ids),
        "qeg_em": average(qeg_rows, "exact_match"),
        "no_path_em": average(baseline_rows, "exact_match"),
        "em_delta": round(average(qeg_rows, "exact_match") - average(baseline_rows, "exact_match"), 6),
        "qeg_f1": average(qeg_rows, "f1"),
        "no_path_f1": average(baseline_rows, "f1"),
        "grounded_answers": grounded,
        "qeg_only_correct": qeg_only,
        "no_path_only_correct": baseline_only,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qeg", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--candidate-label", default="QEG soft contract")
    args = parser.parse_args()

    qeg, baseline = _load(args.qeg), _load(args.baseline)
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    strata = {
        "ambiguous": selection["ambiguous_question_ids"],
        "non_ambiguous": selection["non_ambiguous_question_ids"],
    }
    report = {name: _summary(qeg, baseline, ids) for name, ids in strata.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        label = args.candidate_label
        lines = [f"# Stratified {label}-vs-no-path comparison", "", f"| Stratum | N | {label} EM | No-path EM | Delta | {label} F1 | No-path F1 | Grounded answers |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for name, value in report.items():
            percent = lambda item: f"{100 * item:.2f}%"
            lines.append(
                f"| {name} | {value['n']} | {percent(value['qeg_em'])} | "
                f"{percent(value['no_path_em'])} | {percent(value['em_delta'])} | "
                f"{percent(value['qeg_f1'])} | {percent(value['no_path_f1'])} | {value['grounded_answers']} |"
            )
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
