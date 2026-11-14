#!/usr/bin/env python3
"""Summarise QEG evidence-path compliance and paired EM against a baseline."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


FINAL_ANSWER = re.compile(r"FINAL[ _]+ANSWER\s*:", re.IGNORECASE)


def _load(paths: list[Path]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                identifier = str(row.get("id") or "")
                if not identifier:
                    raise ValueError(f"{path}:{line_number} has no benchmark id")
                if identifier in rows:
                    raise ValueError(f"duplicate benchmark id {identifier!r} across inputs")
                rows[identifier] = row
    return rows


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if not total:
        return None
    fraction = successes / total
    denominator = 1 + z * z / total
    centre = (fraction + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((fraction * (1 - fraction) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, centre - spread), 6), round(min(1.0, centre + spread), 6)]


def _stage_answered(response: object) -> bool:
    return bool(FINAL_ANSWER.search(str(response or "")))


def _summary(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    values = list(rows.values())
    answered = [row for row in values if str(row.get("answer") or "").strip()]
    grounded = [row for row in answered if row.get("answer_evidence_verified") is True]
    exact = sum(float(row.get("exact_match") or 0.0) for row in values)
    f1 = sum(float(row.get("f1") or 0.0) for row in values)
    grounded_exact = sum(float(row.get("exact_match") or 0.0) for row in grounded)
    first_audits = [row.get("adaptive_verification", {}).get("first_evidence_path", {}) for row in values]
    second_audits = [row.get("adaptive_verification", {}).get("second_evidence_path", {}) for row in values]
    first_responses = [row.get("adaptive_verification", {}).get("first_response") for row in values]
    second_responses = [row.get("adaptive_verification", {}).get("second_response") for row in values]
    l1_answered = sum(_stage_answered(response) for response in first_responses)
    l2_answered = sum(_stage_answered(response) for response in second_responses)
    l1_path_valid = sum(bool(audit.get("has_grounded_path")) for audit in first_audits)
    l2_path_valid = sum(bool(audit.get("has_grounded_path")) for audit in second_audits)
    citation_recovery = [row.get("citation_recovery", {}) for row in values]
    citation_attempted = sum(bool(item.get("attempted")) for item in citation_recovery)
    citation_grounded = sum(item.get("final_decision") == "grounded" for item in citation_recovery)
    citation_retried = sum(item.get("retry_response") is not None for item in citation_recovery)
    invalid_citations = sum(bool(audit.get("invalid_refs")) for audit in [*first_audits, *second_audits])
    return {
        "n": len(values),
        "answered": len(answered),
        "exact_match": round(exact / len(values), 6) if values else None,
        "f1": round(f1 / len(values), 6) if values else None,
        # Main grounding claim: fraction of emitted answers with a valid,
        # visible KG edge citation.  The Wilson interval prevents claims from
        # a small trial being over-interpreted.
        "grounded_answer_count": len(grounded),
        "grounded_answer_rate_given_answer": round(len(grounded) / len(answered), 6) if answered else None,
        "grounded_answer_rate_given_answer_95ci": _wilson(len(grounded), len(answered)),
        "end_to_end_grounded_answer_rate": round(len(grounded) / len(values), 6) if values else None,
        "end_to_end_grounded_answer_rate_95ci": _wilson(len(grounded), len(values)),
        "exact_match_given_grounded_answer": round(grounded_exact / len(grounded), 6) if grounded else None,
        "l1_final_answer_count": l1_answered,
        "l1_grounded_path_count": l1_path_valid,
        "l2_final_answer_count": l2_answered,
        "l2_grounded_path_count": l2_path_valid,
        "citation_recovery_attempted": citation_attempted,
        "citation_recovery_grounded": citation_grounded,
        "citation_recovery_retried": citation_retried,
        "invalid_citation_count": invalid_citations,
        "contract_rejections": sum(
            bool(row.get("adaptive_verification", {}).get("first_answer_rejected"))
            or bool(row.get("adaptive_verification", {}).get("second_answer_rejected"))
            for row in values
        ),
    }


def _mcnemar(qeg: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]]) -> dict[str, Any]:
    common = sorted(set(qeg) & set(baseline))
    qeg_wins = baseline_wins = both_correct = both_wrong = 0
    for identifier in common:
        qeg_correct = bool(qeg[identifier].get("exact_match"))
        base_correct = bool(baseline[identifier].get("exact_match"))
        if qeg_correct and not base_correct:
            qeg_wins += 1
        elif base_correct and not qeg_correct:
            baseline_wins += 1
        elif qeg_correct:
            both_correct += 1
        else:
            both_wrong += 1
    discordant = qeg_wins + baseline_wins
    if discordant:
        tail = sum(math.comb(discordant, value) for value in range(min(qeg_wins, baseline_wins) + 1)) / 2 ** discordant
        p_value = min(1.0, 2 * tail)
    else:
        p_value = 1.0
    return {
        "paired_n": len(common),
        "qeg_only_correct": qeg_wins,
        "baseline_only_correct": baseline_wins,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "paired_em_delta": round((qeg_wins - baseline_wins) / len(common), 6) if common else None,
        "mcnemar_exact_two_sided_p": round(p_value, 8),
    }


def _markdown(summary: dict[str, Any], comparison: dict[str, Any] | None) -> str:
    percent = lambda value: "N/A" if value is None else f"{100 * value:.2f}%"
    lines = [
        "# QEG evidence-grounding report",
        "",
        "A grounded answer has a final answer and an `EVIDENCE_PATH` containing at least one visible KG edge ID with no invalid citation. This measures citation/path validity, not whether the cited evidence entails the gold answer.",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Examples | {summary['n']} |",
        f"| EM | {percent(summary['exact_match'])} |",
        f"| Token F1 | {percent(summary['f1'])} |",
        f"| Answered | {summary['answered']} |",
        f"| Grounded answers | {summary['grounded_answer_count']} |",
        f"| Grounded rate among answers | {percent(summary['grounded_answer_rate_given_answer'])} |",
        f"| End-to-end grounded answer rate | {percent(summary['end_to_end_grounded_answer_rate'])} |",
        f"| EM among grounded answers | {percent(summary['exact_match_given_grounded_answer'])} |",
        f"| L1 final answers / grounded paths | {summary['l1_final_answer_count']} / {summary['l1_grounded_path_count']} |",
        f"| L2 final answers / grounded paths | {summary['l2_final_answer_count']} / {summary['l2_grounded_path_count']} |",
        f"| CITE_EVIDENCE attempted / grounded / retried | {summary['citation_recovery_attempted']} / {summary['citation_recovery_grounded']} / {summary['citation_recovery_retried']} |",
        f"| Invalid citations | {summary['invalid_citation_count']} |",
        f"| Contract rejections | {summary['contract_rejections']} |",
    ]
    if comparison is not None:
        lines.extend([
            "",
            "## Paired EM against baseline",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Shared examples | {comparison['paired_n']} |",
            f"| QEG correct, baseline wrong | {comparison['qeg_only_correct']} |",
            f"| Baseline correct, QEG wrong | {comparison['baseline_only_correct']} |",
            f"| Paired EM delta | {percent(comparison['paired_em_delta'])} |",
            f"| Exact two-sided McNemar p | {comparison['mcnemar_exact_two_sided_p']:.8f} |",
        ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True, help="QEG JSONL result files")
    parser.add_argument("--baseline", type=Path, nargs="*", default=[], help="Optional paired baseline JSONL files")
    parser.add_argument("--output", type=Path, help="Write structured JSON report")
    parser.add_argument("--markdown", type=Path, help="Write a concise Markdown report")
    args = parser.parse_args()

    qeg = _load(args.input)
    baseline = _load(args.baseline) if args.baseline else None
    summary = _summary(qeg)
    comparison = _mcnemar(qeg, baseline) if baseline is not None else None
    report = {"qeg": summary, "paired_comparison": comparison}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(_markdown(summary, comparison), encoding="utf-8")


if __name__ == "__main__":
    main()
