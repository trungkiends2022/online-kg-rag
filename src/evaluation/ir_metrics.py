"""Auditable program- and evidence-level metrics for numerical IR."""

from __future__ import annotations

import re
from typing import Any, Iterable

from src.baselines.metrics import finqa_ratio_percentage_match
from src.kg.schema import EvidenceRef


_CALL_RE = re.compile(r"([a-zA-Z_][\w]*)\(([^()]*)\)")
_ARITHMETIC = {"add", "subtract", "multiply", "divide", "exp", "greater"}


def execute_finqa_gold_program(program: str | None) -> list[dict[str, Any]] | None:
    """Execute FinQA's linear gold DSL and expose each intermediate value.

    Returns ``None`` when the annotation uses an unsupported/non-linear form, so
    callers never turn unavailable supervision into a false zero.
    """
    if not program:
        return None
    calls = _CALL_RE.findall(program)
    if not calls:
        return None
    values: list[Any] = []
    trace: list[dict[str, Any]] = []

    def operand(token: str) -> float:
        token = token.strip()
        if token.startswith("#"):
            return float(values[int(token[1:])])
        if token.startswith("const_"):
            token = token[6:]
        return float(token.replace(",", ""))

    try:
        for op, raw_args in calls:
            if op not in _ARITHMETIC:
                return None
            args = [operand(item) for item in raw_args.split(",")]
            if len(args) != 2:
                return None
            if op == "add":
                value = args[0] + args[1]
            elif op == "subtract":
                value = args[0] - args[1]
            elif op == "multiply":
                value = args[0] * args[1]
            elif op == "divide":
                value = args[0] / args[1]
            elif op == "exp":
                value = args[0] ** args[1]
            else:
                value = args[0] > args[1]
            values.append(value)
            trace.append({"operator": op, "value": value})
    except (ValueError, IndexError, ZeroDivisionError, OverflowError):
        return None
    return trace


def _field(evidence: EvidenceRef | dict[str, Any], name: str) -> Any:
    return evidence.get(name) if isinstance(evidence, dict) else getattr(evidence, name)


def _canonical_evidence(evidence: EvidenceRef | dict[str, Any]) -> str | None:
    source_type = _field(evidence, "source_type")
    row_index = _field(evidence, "row_index")
    source_id = _field(evidence, "source_id")
    if source_type == "table" and row_index is not None:
        # FinQA gold_inds counts the header as table_0, whereas KG provenance
        # indexes the normalized data rows from zero.
        return f"table_{int(row_index) + 1}"
    match = re.search(r":(pre|post):(\d+)$", str(source_id))
    if match:
        return f"{match.group(1)}_text_{match.group(2)}"
    return None


def grounding_metrics(
    predicted: Iterable[EvidenceRef | dict[str, Any]], gold_evidence: dict[str, Any] | None,
) -> dict[str, float | None]:
    gold = set((gold_evidence or {}).keys())
    prediction = {item for evidence in predicted if (item := _canonical_evidence(evidence))}
    if not gold:
        return {"grounding_precision": None, "grounding_recall": None}
    overlap = gold & prediction
    return {
        "grounding_precision": len(overlap) / len(prediction) if prediction else 0.0,
        "grounding_recall": len(overlap) / len(gold),
    }


def numerical_ir_metrics(
    predicted_program: dict[str, Any] | None,
    step_values: dict[str, Any] | None,
    gold_program: str | None,
    predicted_evidence: Iterable[EvidenceRef | dict[str, Any]],
    gold_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare canonical arithmetic steps; ignore lookup/const during alignment."""
    metrics: dict[str, Any] = grounding_metrics(predicted_evidence, gold_evidence)
    gold_trace = execute_finqa_gold_program(gold_program)
    if not predicted_program or step_values is None or gold_trace is None:
        metrics.update(operator_accuracy=None, step_accuracy=None, aligned_steps=0)
        return metrics
    predicted_steps = [
        step for step in predicted_program.get("steps", [])
        if step.get("op") in _ARITHMETIC
    ]
    aligned = min(len(predicted_steps), len(gold_trace))
    if not aligned:
        metrics.update(operator_accuracy=0.0, step_accuracy=0.0, aligned_steps=0)
        return metrics
    operator_correct = 0
    step_correct = 0
    for predicted, gold in zip(predicted_steps, gold_trace):
        same_operator = predicted.get("op") == gold["operator"]
        operator_correct += int(same_operator)
        predicted_value = step_values.get(str(predicted.get("id")))
        step_correct += int(
            same_operator
            and finqa_ratio_percentage_match(gold["value"], predicted_value) == 1.0
        )
    denominator = max(len(predicted_steps), len(gold_trace))
    metrics.update(
        operator_accuracy=operator_correct / denominator,
        step_accuracy=step_correct / denominator,
        aligned_steps=aligned,
        predicted_arithmetic_steps=len(predicted_steps),
        gold_arithmetic_steps=len(gold_trace),
    )
    return metrics
