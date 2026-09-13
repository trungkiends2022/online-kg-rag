"""HybridQA-compatible Exact Match and token-level F1 metrics."""

from __future__ import annotations

import re
import string
import math
from collections import Counter
from typing import Any


def normalize_answer(value: Any) -> str:
    text = str(value).lower()
    text = "".join(character for character in text if character not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def exact_match(gold: Any, prediction: Any) -> float:
    return float(normalize_answer(gold) == normalize_answer(prediction))


def token_f1(gold: Any, prediction: Any) -> float:
    gold_tokens = normalize_answer(gold).split()
    prediction_tokens = normalize_answer(prediction).split()
    if not gold_tokens or not prediction_tokens:
        return float(gold_tokens == prediction_tokens)
    overlap = sum((Counter(gold_tokens) & Counter(prediction_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(prediction_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def extract_last_number(value: Any) -> float | None:
    """Extract a final numeric answer from either a scalar or natural-language reply."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    matches = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", str(value))
    if not matches:
        return None
    return float(matches[-1].replace(",", ""))


def finqa_execution_match(gold: Any, prediction: Any) -> float:
    """Match FinQA execution results after the official five-decimal rounding."""
    gold_text = str(gold).strip().lower()
    prediction_text = str(prediction).strip().lower().rstrip(".! ")
    if gold_text in {"yes", "no"}:
        return float(prediction_text == gold_text)
    gold_number = extract_last_number(gold)
    prediction_number = extract_last_number(prediction)
    if gold_number is None or prediction_number is None:
        return 0.0
    return float(round(gold_number, 5) == round(prediction_number, 5))


def finqa_ratio_percentage_match(gold: Any, prediction: Any) -> float:
    """Treat ratio and percentage-point forms as semantically equivalent.

    The strict official score remains available through ``finqa_execution_match``.
    This metric additionally accepts ``x``, ``100*x`` and ``x/100`` after FinQA's
    five-decimal rounding convention.
    """
    if finqa_execution_match(gold, prediction):
        return 1.0
    gold_number = extract_last_number(gold)
    prediction_number = extract_last_number(prediction)
    if gold_number is None or prediction_number is None:
        return 0.0
    return float(
        round(gold_number, 5) == round(prediction_number / 100.0, 5)
        or round(gold_number / 100.0, 5) == round(prediction_number, 5)
    )
