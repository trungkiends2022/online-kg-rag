"""Question/schema-derived numerical intent constraints without gold labels."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.kg.online_kg import OnlineKG


def infer_operation_intent(question: str, kg: "OnlineKG") -> dict[str, Any]:
    """Return conservative operator guidance derived only from inference input."""
    text = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    relations = kg.summary().get("relations", [])
    has_percentage_cells = any(
        "percentage" in relation or "percent" in relation for relation in relations
    )
    preferred: list[str] = []
    constraints: list[str] = []

    combined_terms = (" combined" in f" {text}") or "together" in text
    asks_proportion = "proportion" in text or "percent" in text or "percentage" in text
    if combined_terms and asks_proportion and has_percentage_cells:
        preferred.append("add")
        constraints.append(
            "The table already provides percentage/proportion cells for the named groups. "
            "For 'combined' or 'together', add those displayed percentage cells directly. "
            "Do not recompute a weighted rate from count columns unless the question explicitly "
            "asks for a share of a combined population or a denominator."
        )
    if "average" in text or "on average" in text:
        preferred.append("table_average")
        constraints.append("Average the requested displayed values; do not sum them.")
    if any(term in text for term in ("highest", "largest", "most ")):
        preferred.append("argmax")
    if any(term in text for term in ("lowest", "smallest", "least ")):
        preferred.append("argmin")
    if re.search(r"\btop\s+\d+\b", text):
        preferred.append("topk_argmax")
    if re.search(r"\b(second|third|fourth)\s+(largest|highest)\b", text):
        preferred.append("kth_argmax")
    if re.search(r"\b(second|third|fourth)\s+(smallest|lowest)\b", text):
        preferred.append("kth_argmin")
    if "range" in text:
        preferred.append("range")
        constraints.append("For HiTab range denotations, return [maximum, minimum].")
    if re.search(r"\bhow many\b", text) and any(term in text for term in ("reported", "countries", "provinces", "territories", "groups")):
        preferred.append("count")
    if any(term in text for term in ("difference", "increase", "decline", "decrease")):
        preferred.append("subtract")
    if any(term in text for term in ("outperform", "greater than", "higher than")):
        preferred.append("greater")
        constraints.append(
            "This is a comparison question. Retrieve both compared values and execute "
            "greater(left, right); return the grounded boolean as yes or no."
        )
    if asks_proportion and not combined_terms:
        preferred.append("divide")
        constraints.append(
            "For a share or percentage, retrieve both the numerator and denominator. "
            "Normalize explicitly stated text units before division; multiply by 100 only "
            "when returning a percentage rather than a ratio."
        )
    if re.search(r"\bfrom\b.+\bto\b", text):
        constraints.append(
            "For temporal change from A to B, preserve the sign and calculate B minus A."
        )
    if "sum" in text or (combined_terms and not asks_proportion):
        preferred.append("add")
    if "total" in text:
        constraints.append(
            "The word 'total' may name an existing row/cell rather than request addition. "
            "Prefer an exact total entity when present; use table_sum only when the question "
            "asks to aggregate a displayed row or set."
        )

    return {
        "source": "question_and_kg_schema",
        "preferred_operators": list(dict.fromkeys(preferred)),
        "constraints": constraints,
    }


def format_operation_intent(intent: dict[str, Any]) -> str:
    if not intent.get("preferred_operators") and not intent.get("constraints"):
        return "No additional operation constraint inferred."
    operators = ", ".join(intent.get("preferred_operators", [])) or "unspecified"
    rules = " ".join(intent.get("constraints", []))
    return f"Preferred operators: {operators}. Constraints: {rules}"
