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
    if any(term in text for term in ("difference", "increase", "decline", "decrease")):
        preferred.append("subtract")
    if re.search(r"\bfrom\b.+\bto\b", text):
        constraints.append(
            "For temporal change from A to B, preserve the sign and calculate B minus A."
        )
    if "total" in text or "sum" in text:
        preferred.append("add")

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
