#!/usr/bin/env python3
"""Apply deterministic ECAR to existing HybridQA/OUEG JSONL predictions.

This is an offline ablation runner: it reads only a prediction's retrieved KG
trace and reader answer.  It never accesses ``gold_answer`` during recovery;
that field is used only afterwards to recompute evaluation metrics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

# `python scripts/replay_ecar.py` sets sys.path to `scripts/`, whereas the
# project packages live at the repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.baselines.ecar import EvidenceConstrainedAnswerRecovery
from src.baselines.metrics import exact_match, semantic_exact_match, token_f1


def _answer_key(value: object) -> str:
    """Conservative equality key for checking an ECAR audit against L1."""
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--preserve-answer", action="store_true",
        help=(
            "Answer-to-Proof mode: retain the cached no-path L1 answer exactly; "
            "ECAR may only attach a proof for the same denotation."
        ),
    )
    args = parser.parse_args()

    rows, changed, deterministic = [], 0, 0
    for line_number, line in enumerate(args.input.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        trace = row.get("full_kg")
        if not isinstance(trace, dict):
            raise ValueError(f"{args.input}:{line_number} has no full_kg trace")
        old_answer = str(row.get("answer") or "")
        ecar = EvidenceConstrainedAnswerRecovery.recover(
            question=str(row.get("question") or ""), llm_answer=old_answer, kg_trace=trace,
        )
        same_denotation = (
            _answer_key(ecar["answer"]) == _answer_key(old_answer)
        )
        answer = old_answer if args.preserve_answer else ecar["answer"]
        changed += answer != old_answer
        deterministic += ecar["decision"] == "deterministic_recovery"
        row["method"] = (
            "qeg_ecar_answer_to_proof_replay" if args.preserve_answer else "qeg_ecar_replay"
        )
        row["answer_before_ecar"] = old_answer
        row["answer"] = answer
        row["ecar"] = ecar
        row["answer_to_proof"] = {
            "reader_answer": old_answer,
            "same_denotation": same_denotation,
            "ecar_audit": ecar,
        }
        row["answer_evidence_path"] = ecar.get("selected") if same_denotation else None
        row["answer_evidence_verified"] = bool(
            same_denotation and ecar.get("evidence_verified")
        )
        row["evidence_contract"] = {
            "mode": (
                "answer_preserving_deterministic_ecar"
                if args.preserve_answer else "deterministic_ecar"
            ),
            "required": False,
            "satisfied": bool(row["answer_evidence_verified"]),
        }
        gold, question = row.get("gold_answer"), row.get("question")
        row["exact_match"] = exact_match(gold, answer)
        row["semantic_exact_match"] = semantic_exact_match(gold, answer, question=question)
        row["f1"] = token_f1(gold, answer)
        rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8",
    )
    print(json.dumps({
        "input": str(args.input), "output": str(args.output), "n": len(rows),
        "changed_answers": changed, "deterministic_recoveries": deterministic,
        "preserve_answer": args.preserve_answer,
        "exact_match": round(sum(row["exact_match"] for row in rows) / len(rows), 6) if rows else None,
        "f1": round(sum(row["f1"] for row in rows) / len(rows), 6) if rows else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
