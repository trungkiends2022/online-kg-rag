"""HybridQA-compatible Exact Match and token-level F1 metrics."""

from __future__ import annotations

import re
import string
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
