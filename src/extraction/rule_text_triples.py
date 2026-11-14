"""Deterministic Wikipedia-style passage-to-triple extraction."""

from __future__ import annotations

import re

from src.kg.schema import Provenance, Triple


def _clean_entity(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" ,.;:"))


def _subject_entity(value: str) -> str:
    return re.sub(r"\s+(?:city|town|village)$", "", _clean_entity(value), flags=re.IGNORECASE)


def extract_rule_text_triples(
    passage_id: str, text: str, *, context_before: str = "",
) -> list[Triple]:
    """Extract high-precision facts from recurring encyclopedic sentence forms."""
    provenance = Provenance("text", passage_id, text[:200], source_group="rule_text")
    triples: list[Triple] = []
    seen: set[tuple[str, str, str]] = set()

    def emit(head: str, relation: str, tail: str) -> None:
        head = _clean_entity(head)
        tail = _clean_entity(tail)
        key = (head, relation, tail)
        if head and tail and head != tail and key not in seen:
            triples.append(Triple(head, relation, tail, provenance))
            seen.add(key)

    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence = sentence.strip()
        if not sentence:
            continue
        between = re.search(
            r"(?P<head>[A-Z][A-Za-z0-9 .,'’()-]{0,100}?)\s*,?\s+(?:is|was)\s+situated\s+between\s+"
            r"(?P<left>[A-Z][A-Za-z0-9 .,'’()-]{0,80}?)\s+and\s+(?P<right>[A-Z][A-Za-z0-9 .,'’()-]{0,80}?)(?=\s*(?:,|;|\.|$))",
            sentence,
        )
        if between:
            head = _subject_entity(between.group("head"))
            left = _clean_entity(between.group("left"))
            right = _clean_entity(between.group("right"))
            emit(head, "situated_between", f"{left} and {right}")
            emit(head, "situated_between_landmark", left)
            emit(head, "situated_between_landmark", right)

        based = re.search(
            r"(?P<head>[A-Z][A-Za-z0-9 .,'’()-]{0,100}?)\s+(?:is|was)\s+(?:an?\s+)?[^.]{0,70}?\bbased\s+in\s+(?P<tail>[A-Z][A-Za-z0-9 .,'’()-]{0,80}?)(?=\s*(?:,|;|\.|$))",
            sentence,
        )
        if based:
            emit(_subject_entity(based.group("head")), "based_in", based.group("tail"))

        located = re.search(
            r"(?P<head>[A-Z][A-Za-z0-9 .,'’()-]{0,100}?)\s*,?\s+(?:is|was)\s+(?:located|situated)\s+in\s+(?P<tail>[A-Z][A-Za-z0-9 .,'’()-]{0,80}?)(?=\s*(?:,|;|\.|$))",
            sentence,
        )
        if located:
            emit(_subject_entity(located.group("head")), "located_in", located.group("tail"))

    return triples
