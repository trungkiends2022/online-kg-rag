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
_QUESTION_ENTITY_COLUMNS = (
    "jurisdiction", "country", "city", "state", "province", "region", "company",
    "organization", "team", "club", "player", "person", "name",
)


@dataclass(frozen=True)
class EntityAnchor:
    direct_mentions: tuple[str, ...]
    entity_type: str | None
    target_attribute: str | None
    constraints: dict[str, str]
    bridge_entities: tuple[str, ...]
    table_constraints: tuple[dict[str, Any], ...] = ()
    table_witnesses: tuple[dict[str, Any], ...] = ()

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
        # A substring test classifies "whose" as "who", which corrupts
        # entity-centric retrieval for questions such as "Which country whose…".
        (r"\bwho\b", "person"),
    ):
        if re.search(phrase, lowered) if phrase.startswith("\\b") else phrase in lowered:
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


def _question_literals(question: str) -> tuple[str, ...]:
    """Return exact numeric-like constraints that can safely match table cells."""
    literals: list[str] = []
    for pattern in (
        r"\b\d+(?:\.\d+)?\s*%",
        r"(?<![\w.])\$\s*\d+(?:[,.]\d+)*(?:\s*(?:million|billion|thousand))?",
        r"\b(?:19|20)\d{2}\b",
    ):
        for match in re.findall(pattern, question, flags=re.IGNORECASE):
            literal = _clean(match)
            if literal and literal not in literals:
                literals.append(literal)
    return tuple(literals)


def _literal_matches(value: Any, literal: str) -> bool:
    """Match a question literal only to an entire table cell, never a substring."""
    def canonical(text: Any) -> str:
        # HybridQA tokenization may render the same percentage as ``21 %`` in
        # the question and ``21%`` in a table cell.
        return re.sub(r"\s+%", "%", _clean(text).casefold())

    return canonical(value) == canonical(literal)


def _answer_column(row: dict[str, Any], question: str) -> str | None:
    """Prefer the table column explicitly requested by the question."""
    lowered = question.casefold()
    for key in row:
        key_text = _clean(key)
        key_lower = key_text.casefold()
        if key_lower in lowered and any(token in key_lower for token in _QUESTION_ENTITY_COLUMNS):
            return key_text
    for key in row:
        key_text = _clean(key)
        if any(token in key_text.casefold() for token in _QUESTION_ENTITY_COLUMNS):
            return key_text
    return next(iter(row), None)


def _question_requests_column(question: str, column: str) -> bool:
    """Whether the answer is explicitly expected to be a value of this column."""
    lowered = question.casefold()
    if not re.search(r"\b(?:which|what|who)\b", lowered):
        return False
    column_key = _clean(column).casefold()
    if not column_key:
        return False
    target_match = re.search(r"\b(?:which|what|who)\s+(?:'s\s+)?([a-z0-9_]+)", lowered)
    if target_match:
        requested_target = target_match.group(1)
        if (
            requested_target in {"country", "city", "state", "province", "region", "jurisdiction", "nation"}
            and column_key != requested_target
        ):
            return False
    return bool(re.search(rf"\b{re.escape(column_key)}\b", lowered))



def _table_value_constraints(question: str, table_rows: list[dict]) -> tuple[dict[str, Any], ...]:
    """Resolve table literals to candidate answer entities.

    A literal can occur in more than one column.  Prefer the column whose header
    overlaps most with the question (``standard rate`` over ``reduced rate``),
    then preserve all entities matching that column.  This creates an explicit,
    inspectable candidate set for table -> text multi-hop questions.
    """
    literals = _question_literals(question)
    if not literals:
        return ()
    question_terms = set(re.findall(r"[a-z0-9]+", question.casefold()))
    constraints: list[dict[str, Any]] = []
    for literal in literals:
        matches: list[tuple[int, str, str, list[str]]] = []
        for group in table_rows:
            for row in group.get("rows", []):
                candidate_key = _answer_column(row, question)
                if not candidate_key or not _clean(row.get(candidate_key, "")):
                    continue
                for key, value in row.items():
                    if not _literal_matches(value, literal):
                        continue
                    header = _clean(key)
                    header_terms = set(re.findall(r"[a-z0-9]+", header.casefold()))
                    overlap = len(header_terms & question_terms)
                    matches.append((overlap, header, candidate_key, [_clean(row[candidate_key])]))
        if not matches:
            continue
        best_overlap = max(item[0] for item in matches)
        grouped: dict[tuple[str, str], list[str]] = {}
        for overlap, header, candidate_key, candidates in matches:
            if overlap != best_overlap:
                continue
            grouped.setdefault((header, candidate_key), []).extend(candidates)
        for (header, candidate_key), candidates in grouped.items():
            unique = tuple(dict.fromkeys(candidate for candidate in candidates if candidate))
            if unique:
                constraints.append({
                    "column": header,
                    "value": literal,
                    "entity_column": candidate_key,
                    "candidates": unique,
                    "enforce_output": _question_requests_column(question, candidate_key),
                })
    return tuple(constraints)


def anchor_question(
    question: str,
    table_rows: list[dict],
    text_passages: list[dict] | None = None,
) -> EntityAnchor:
    """Return question constraints and table-derived bridge entities.

    ``table_rows`` uses the repository's grouped-table schema.  The rank rule
    intentionally supports the common HybridQA pattern "the second most …".
    More anchor extractors can be added without changing retrieval callers.
    """
    from src.planning.table_operator import TableOperatorPlanner

    rank = _rank_constraint(question)
    constraints: dict[str, str] = {}
    if rank is not None:
        constraints["rank"] = rank

    bridge_entities: list[str] = []
    witnesses = TableOperatorPlanner().plan(question, table_rows, text_passages)
    witness_dicts = tuple(w.to_dict() for w in witnesses)

    for w in witnesses:
        for entity in w.bridge_entities:
            if entity and entity not in bridge_entities:
                bridge_entities.append(entity)

    if rank is not None:
        for group in table_rows:
            for row in group.get("rows", []):
                for key, value in row.items():
                    if "rank" in key.casefold() and _clean(value).casefold() == rank:
                        entity = _row_entity(row)
                        if entity and entity not in bridge_entities:
                            bridge_entities.append(entity)

    table_constraints_list = list(_table_value_constraints(question, table_rows))
    for w in witnesses:
        table_constraints_list.append({
            "column": w.evidence_columns[0] if w.evidence_columns else "operator",
            "value": w.operator,
            "entity_column": "witness",
            "candidates": list(w.bridge_entities),
            "enforce_output": False,
            "witness": w.to_dict(),
        })

    for constraint in table_constraints_list:
        for entity in constraint["candidates"]:
            if entity not in bridge_entities:
                bridge_entities.append(entity)

    table_constraints = tuple(table_constraints_list)
    direct_mentions = tuple(re.findall(r"\b[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)+\b", question))
    return EntityAnchor(
        direct_mentions=direct_mentions,
        entity_type=_entity_type(question),
        target_attribute=_target_attribute(question),
        constraints=constraints,
        bridge_entities=tuple(bridge_entities),
        table_constraints=table_constraints,
        table_witnesses=witness_dicts,
    )

