"""Deterministic question anchors for entity-centric table--text retrieval.

The anchor is deliberately small and inspectable: it extracts constraints from
the question and resolves table entities that satisfy those constraints.  It is
used to retrieve a linked passage *after* a table row identifies the bridge
entity, rather than relying on lexical BM25 over the original question alone.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


_ORDINALS = {
    "first": "1", "second": "2", "third": "3", "fourth": "4",
    "fifth": "5", "sixth": "6", "seventh": "7", "eighth": "8",
    "ninth": "9", "tenth": "10",
}
_ENTITY_COLUMNS = ("player", "person", "name", "manager", "team", "club", "entity")


@dataclass(frozen=True)
class EntityAnchor:
    direct_mentions: tuple[str, ...]
    entity_type: str | None
    target_attribute: str | None
    constraints: dict[str, str]
    bridge_entities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _target_attribute(question: str) -> str | None:
    lowered = question.casefold()
    for phrase, attribute in (
        ("middle name", "middle_name"),
        ("full name", "full_name"),
        ("nationality", "nationality"),
        ("born", "birth_date"),
        ("place of birth", "place_of_birth"),
        ("where", "location"),
        ("who", "person"),
    ):
        if phrase in lowered:
            return attribute
    return None


def _entity_type(question: str) -> str | None:
    lowered = question.casefold()
    for keyword, entity_type in (
        ("player", "person"), ("manager", "person"), ("person", "person"),
        ("team", "team"), ("club", "club"), ("city", "location"),
        ("country", "location"),
    ):
        if keyword in lowered:
            return entity_type
    return None


def _rank_constraint(question: str) -> str | None:
    lowered = question.casefold()
    for word, value in _ORDINALS.items():
        if re.search(rf"\b{word}\b", lowered):
            return value
    match = re.search(r"\b(\d+)(?:st|nd|rd|th)\b", lowered)
    return match.group(1) if match else None


def _row_entity(row: dict[str, Any]) -> str | None:
    for key, value in row.items():
        if any(column in key.casefold() for column in _ENTITY_COLUMNS):
            candidate = _clean(value)
            if candidate:
                return candidate
    for key, value in row.items():
        if "rank" not in key.casefold() and _clean(value):
            return _clean(value)
    return None


def anchor_question(question: str, table_rows: list[dict]) -> EntityAnchor:
    """Return question constraints and table-derived bridge entities.

    ``table_rows`` uses the repository's grouped-table schema.  The rank rule
    intentionally supports the common HybridQA pattern "the second most …".
    More anchor extractors can be added without changing retrieval callers.
    """
    rank = _rank_constraint(question)
    constraints: dict[str, str] = {}
    if rank is not None:
        constraints["rank"] = rank

    bridge_entities: list[str] = []
    if rank is not None:
        for group in table_rows:
            for row in group.get("rows", []):
                for key, value in row.items():
                    if "rank" in key.casefold() and _clean(value).casefold() == rank:
                        entity = _row_entity(row)
                        if entity and entity not in bridge_entities:
                            bridge_entities.append(entity)

    direct_mentions = tuple(re.findall(r"\b[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)+\b", question))
    return EntityAnchor(
        direct_mentions=direct_mentions,
        entity_type=_entity_type(question),
        target_attribute=_target_attribute(question),
        constraints=constraints,
        bridge_entities=tuple(bridge_entities),
    )
