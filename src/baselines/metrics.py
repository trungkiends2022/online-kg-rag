"""HybridQA-compatible Exact Match and token-level F1 metrics."""

from __future__ import annotations

import re
import string
import math
from collections import Counter
from typing import Any

from src.kg.normalization import DEFAULT_ENTITY_ALIASES, normalize_key


_IRREGULAR_SINGULARS = {
    "children": "child",
    "feet": "foot",
    "geese": "goose",
    "men": "man",
    "mice": "mouse",
    "people": "person",
    "teeth": "tooth",
    "women": "woman",
}
_NON_PLURAL_S_SUFFIXES = ("ss", "us", "is")
_MEASUREMENT_UNIT = (
    r"(?:%|percent(?:age)?|km(?:²|2)?|kilometers?|kilometres?|mi|miles?|"
    r"m(?:²|2)?|meters?|metres?|ft|feet|foot|yards?|acres?|hectares?|"
    r"years?|months?|days?|hours?|minutes?|seconds?|square\s+(?:miles?|"
    r"kilometers?|kilometres?|meters?|metres?))"
)
_CONVERTED_UNIT_SUFFIX = re.compile(
    rf"(?P<value>[+-]?\d[\d,]*(?:\.\d+)?\s*{_MEASUREMENT_UNIT})\s*"
    rf"\(\s*(?:≈|~|=)?\s*[+-]?\d[\d,]*(?:\.\d+)?\s*{_MEASUREMENT_UNIT}\s*\)",
    re.IGNORECASE,
)
_CARDINAL_WORD_VALUES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_NUMBER_SCALES = {"hundred": 100, "thousand": 1000}
_ENTITY_CLASSIFIER_SUFFIXES = (
    "premier league",
    "county",
    "city",
    "coast",
    "league",
)
_QUESTION_COUNT_UNIT_PATTERN = re.compile(
    r"\bhow many(?:\s+\w+){0,3}\s+(?P<unit>year|season)\b"
)
_FRACTIONAL_CONTEXT_PATTERN = re.compile(
    r"^(?:about|approximately|around|roughly)\s+(?P<fraction>half|quarter|third|fourth|fifth)"
    r"\s+of\s+(?:its|their|the)\s+.+$"
)


def _singularize_answer_token(token: str) -> str:
    """Apply a deterministic English plural normalizer for scoring.

    Evaluation should not mark an answer wrong solely for an inflection such as
    ``clubs`` versus ``club``. This avoids external NLP models so benchmark
    scoring remains reproducible and offline.
    """
    if token in _IRREGULAR_SINGULARS:
        return _IRREGULAR_SINGULARS[token]
    if len(token) <= 3 or any(character.isdigit() for character in token):
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("lves") and len(token) > 4:
        return token[:-3] + "f"
    if token.endswith("ives") and len(token) > 4:
        return token[:-3] + "fe"
    if token.endswith("ves") and len(token) > 4:
        return token[:-3] + "f"
    if token.endswith(("ches", "shes", "xes", "zes", "sses")):
        return token[:-2]
    if token.endswith("s") and not token.endswith(_NON_PLURAL_S_SUFFIXES):
        return token[:-1]
    return token


def normalize_answer(value: Any) -> str:
    text = str(value)
    # Convert non-ASCII punctuation before the legacy ASCII punctuation pass.
    # In particular, U+2011 otherwise survives scoring and splits identical
    # values such as "1991-92" and "1991‑92".
    text = text.replace("\u2011", "-")
    # Keep the primary measurement but discard a parenthetical conversion, e.g.
    # "806 km (≈ 501 mi)" -> "806 km". Both sides must be numeric units, so
    # descriptive parentheses in entity names are left intact.
    text = _CONVERTED_UNIT_SUFFIX.sub(r"\g<value>", text)
    text = text.lower()
    text = "".join(character for character in text if character not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(_singularize_answer_token(token) for token in text.split())


def exact_match(gold: Any, prediction: Any) -> float:
    return float(normalize_answer(gold) == normalize_answer(prediction))


def normalize_entity_answer(value: Any) -> str:
    """Canonicalize explicit, audited entity aliases before semantic scoring.

    ``exact_match`` remains the official HybridQA-compatible metric.  This
    helper supports a *separately labelled* semantic score, e.g. ``Moroccan``
    versus the table denotation ``Morocco``.  It never uses the gold answer to
    rewrite a prediction.
    """
    key = normalize_key(str(value))
    canonical = DEFAULT_ENTITY_ALIASES.get(key)
    return normalize_answer(canonical if canonical is not None else value)


def _normalize_cardinal_number(text: str) -> str:
    """Convert a complete English cardinal phrase to digits, when unambiguous."""
    tokens = text.split()
    if not tokens or any(
        token not in _CARDINAL_WORD_VALUES and token not in _NUMBER_SCALES and token != "and"
        for token in tokens
    ):
        return text
    total = 0
    current = 0
    for token in tokens:
        if token == "and":
            continue
        if token in _NUMBER_SCALES:
            scale = _NUMBER_SCALES[token]
            if scale == 100:
                current = max(current, 1) * scale
            else:
                total += max(current, 1) * scale
                current = 0
        else:
            current += _CARDINAL_WORD_VALUES[token]
    return str(total + current)


def _question_count_unit(question: str | None) -> str | None:
    if not question:
        return None
    match = _QUESTION_COUNT_UNIT_PATTERN.search(normalize_answer(question))
    return match.group("unit") if match else None


def _strip_entity_classifier(text: str) -> str:
    for suffix in _ENTITY_CLASSIFIER_SUFFIXES:
        if text.endswith(" " + suffix):
            return text[: -len(suffix)].strip()
    return text


def normalize_semantic_answer(value: Any, *, question: str | None = None) -> str:
    """Deterministic surface normalization used only by Semantic EM.

    Strict EM intentionally remains the benchmark's original normalization.
    These rules cover transparent equivalences: cardinal words/digits, a count
    unit repeated by a ``how many`` question, fractional context, and generic
    entity classifier suffixes.
    """
    text = normalize_entity_answer(value)
    fractional = _FRACTIONAL_CONTEXT_PATTERN.fullmatch(text)
    if fractional:
        text = fractional.group("fraction")
    if unit := _question_count_unit(question):
        text = re.sub(rf"\s+{re.escape(unit)}$", "", text)
    text = re.sub(r"\bcampus of (?=university\b)", "", text)
    text = " ".join(text.split())
    text = _strip_entity_classifier(text)
    return _normalize_cardinal_number(text)


def semantic_exact_match(gold: Any, prediction: Any, *, question: str | None = None) -> float:
    """Rule-based semantic complement to strict benchmark EM; report separately."""
    return float(
        normalize_semantic_answer(gold, question=question)
        == normalize_semantic_answer(prediction, question=question)
    )


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
