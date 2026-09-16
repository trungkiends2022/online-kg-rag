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
    prediction_text = (
        "yes" if prediction is True else "no" if prediction is False
        else str(prediction).strip().lower().rstrip(".! ")
    )
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


def hitab_strict_denotation_match(gold: Any, prediction: Any) -> float:
    """Match HiTab denotations without changing numeric scale."""
    gold_values = gold if isinstance(gold, (list, tuple)) else [gold]
    prediction_values = prediction if isinstance(prediction, (list, tuple)) else [prediction]
    if len(gold_values) == len(prediction_values) == 1:
        gold_number = extract_last_number(gold_values[0])
        predicted_number = extract_last_number(prediction_values[0])
        if gold_number is not None and predicted_number is not None:
            return float(math.isclose(gold_number, predicted_number, rel_tol=1e-5, abs_tol=1e-5))
        return exact_match(gold_values[0], prediction_values[0])
    normalized_gold = sorted(normalize_answer(value) for value in gold_values)
    normalized_prediction = sorted(normalize_answer(value) for value in prediction_values)
    return float(normalized_gold == normalized_prediction)


def hitab_denotation_match(gold: Any, prediction: Any) -> float:
    """Match HiTab denotations, treating ratio and percent forms as equivalent.

    ``hitab_strict_denotation_match`` remains available for reporting the
    unmodified benchmark-scale score alongside this semantic score.
    """
    if hitab_strict_denotation_match(gold, prediction):
        return 1.0
    gold_values = gold if isinstance(gold, (list, tuple)) else [gold]
    prediction_values = prediction if isinstance(prediction, (list, tuple)) else [prediction]
    if len(gold_values) != 1 or len(prediction_values) != 1:
        return 0.0
    gold_number = extract_last_number(gold_values[0])
    predicted_number = extract_last_number(prediction_values[0])
    if gold_number is None or predicted_number is None:
        return 0.0
    return float(
        math.isclose(gold_number, predicted_number / 100.0, rel_tol=1e-5, abs_tol=1e-5)
        or math.isclose(gold_number / 100.0, predicted_number, rel_tol=1e-5, abs_tol=1e-5)
    )
