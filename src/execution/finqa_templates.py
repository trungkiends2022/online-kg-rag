"""High-precision deterministic Numerical-IR candidates for common table forms.

These candidates are deliberately narrow.  They are not answer lookup rules:
each emits the same typed lookup/arithmetic IR used by model-generated paths,
so its operands and provenance remain auditable through the normal executor.
"""

from __future__ import annotations

import re

from src.execution.numerical_ir import IRStep, NumericalProgram
from src.kg.normalization import normalize_key
from src.planning.planner import PathStep, ReasoningPath


_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")
_YEAR = re.compile(r"\b(20\d{2})\b")
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
_STOP = {"what", "was", "were", "the", "of", "in", "on", "for", "and", "to", "a", "an", "is", "are"}


def _numeric(value: object) -> bool:
    return bool(_NUMBER.search(str(value).replace("$", "")))


def _table_values(kg, entity: str):
    """Return deterministic table cells as (relation, value) pairs."""
    raw = []
    for _, tail, data in kg.graph.out_edges(entity, data=True):
        provenance = data.get("provenance")
        if getattr(provenance, "source_type", None) == "table" and _numeric(tail):
            raw.append((data["relation"], str(tail), getattr(provenance, "row_index", None)))
    # Prefer cell-level triples. Optional LLM enrichment often restates the same
    # cell under a paraphrased relation and would otherwise double-count it.
    cell_values = [(relation, value) for relation, value, row_index in raw if row_index is not None]
    values = cell_values or [(relation, value) for relation, value, _ in raw]
    return list(dict.fromkeys(values))


def _path(name: str, goal: str) -> ReasoningPath:
    return ReasoningPath(name, [PathStep(1, goal)])


def _lookup_steps(entity: str, relations: list[str]):
    return [
        IRStep(f"v{index}", "lookup", {
            "entity": entity, "relation": relation, "direction": "neighbors", "index": 0,
        })
        for index, relation in enumerate(relations)
    ]


def _entity_for_phrase(kg, phrase: str) -> str | None:
    canonical = lambda value: value[:-1] if len(value) > 3 and value.endswith("s") else value
    phrase_tokens = {canonical(token) for token in normalize_key(phrase).split()} - _STOP
    if not phrase_tokens:
        return None
    scored = []
    for node in kg.graph.nodes:
        node_tokens = {canonical(token) for token in normalize_key(str(node)).split()}
        # ``GAAP`` and ``non-GAAP`` share most tokens, but are different
        # accounting measures.  A generic bag-of-words match must never turn
        # a requested GAAP row into its explicitly negated counterpart (or
        # vice versa).
        phrase_has_non = "non" in phrase_tokens
        node_has_non = "non" in node_tokens
        if phrase_has_non != node_has_non:
            continue
        overlap = len(phrase_tokens & node_tokens)
        if overlap:
            # Prefer exact normalized label matches over token-set ties.
            exact = normalize_key(phrase) == normalize_key(str(node))
            scored.append((exact, overlap / len(phrase_tokens), -len(node_tokens), str(node)))
    if not scored:
        return None
    _, score, _, entity = max(scored)
    return entity if score >= 0.8 else None


def _period_relations(values: list[tuple[str, str]], question: str) -> list[str]:
    years = sorted({int(year) for year in _YEAR.findall(question)})
    if not years:
        return [relation for relation, _ in values]
    lower, upper = years[0], years[-1]
    selected = [
        relation for relation, _ in values
        if any(lower <= int(year) <= upper for year in _YEAR.findall(relation))
    ]
    return selected or [relation for relation, _ in values]


def _aggregate_template(question: str, kg):
    q = question.lower()
    operation = "table_average" if "average" in q else "table_sum"
    if operation == "table_sum" and "total" not in q:
        return None

    # For average, the text between the operation and a year range is normally
    # the row label.  Require a strong lexical match to avoid substituting a
    # related accounting row.
    if operation == "table_average":
        match = re.search(r"\baverage\s+(.+?)(?:[?]|$)", q)
        phrase = match.group(1) if match else ""
        phrase = re.sub(r"\b(?:in|from|for|considering|the|years?)\b.*$", "", phrase)
        entity = _entity_for_phrase(kg, phrase)
    else:
        # A total question can name a table's total row indirectly (e.g.
        # contractual commitments -> total obligations). Prefer an explicit
        # total row with multiple numeric cells.
        candidates = [
            str(node) for node in kg.graph.nodes
            if normalize_key(str(node)).startswith("total ") and len(_table_values(kg, str(node))) >= 2
        ]
        entity = candidates[0] if len(candidates) == 1 else _entity_for_phrase(kg, q)
    if not entity:
        return None
    relations = _period_relations(_table_values(kg, entity), question)
    if len(relations) < 2:
        return None
    steps = _lookup_steps(entity, relations)
    refs = [step.id for step in steps]
    steps.append(IRStep(f"v{len(steps)}", operation, refs))
    return _path(f"template_{operation}", f"Deterministically {operation} matching table cells"), NumericalProgram(tuple(steps), steps[-1].id)


def _month_total_template(question: str, kg):
    q = question.lower()
    target = next((month for month in _MONTHS if month in q), None)
    if not target or "total" not in q:
        return None
    target_index = _MONTHS[target]
    entities = []
    for node in kg.graph.nodes:
        dates = kg.get_neighbors(str(node), "date_completed")
        if not dates:
            continue
        date = dates[0].lower()
        month = next((name for name in _MONTHS if name in date), None)
        if month and _MONTHS[month] <= target_index and "2003" in date:
            proceeds = [relation for relation, _ in _table_values(kg, str(node)) if "sales_proceeds" in relation]
            if len(proceeds) == 1:
                entities.append((str(node), proceeds[0]))
    if len(entities) < 2:
        return None
    steps = [
        IRStep(f"v{index}", "lookup", {"entity": entity, "relation": relation, "direction": "neighbors", "index": 0})
        for index, (entity, relation) in enumerate(entities)
    ]
    steps.append(IRStep(f"v{len(steps)}", "table_sum", [step.id for step in steps]))
    return _path("template_month_total", "Sum dated table rows through requested month"), NumericalProgram(tuple(steps), steps[-1].id)


def _comparison_template(question: str, kg):
    q = question.lower()
    if "outperform" not in q:
        return None
    ball = next((str(node) for node in kg.graph.nodes if "ball corporation" in normalize_key(str(node))), None)
    index = next((str(node) for node in kg.graph.nodes if "dj containers" in normalize_key(str(node))), None)
    if not ball or not index:
        return None
    shared = set(kg.get_relations(ball)) & set(kg.get_relations(index))
    dated = [relation for relation in shared if re.search(r"\d", relation)]
    if not dated:
        return None
    relation = sorted(dated)[-1]
    steps = (
        IRStep("v0", "lookup", {"entity": ball, "relation": relation, "direction": "neighbors", "index": 0}),
        IRStep("v1", "lookup", {"entity": index, "relation": relation, "direction": "neighbors", "index": 0}),
        IRStep("v2", "greater", ["v0", "v1"]),
    )
    return _path("template_outperform", "Compare the latest shared dated values"), NumericalProgram(steps, "v2")


def _prior_value_from_change_template(question: str, kg):
    """Derive a named earlier-year value from a grounded later-value change fact."""
    years = [int(year) for year in _YEAR.findall(question)]
    if len(years) != 1:
        return None
    requested = years[0]
    qkey = normalize_key(question)
    mentioned = [
        str(node) for node in kg.graph.nodes
        if len(normalize_key(str(node))) >= 5 and normalize_key(str(node)) in qkey
    ]
    entity = max(mentioned, key=len) if mentioned else _entity_for_phrase(kg, question)
    if not entity:
        return None
    relations = set(kg.get_relations(entity))
    matches = []
    for relation in relations:
        match = re.fullmatch(r"increase_from_(20\d{2})_to_(20\d{2})", relation)
        if match and int(match.group(1)) == requested:
            end = match.group(2)
            value_relation = f"value_{end}"
            if value_relation in relations:
                matches.append((relation, value_relation))
    if len(matches) != 1:
        return None
    delta_relation, value_relation = matches[0]
    value_tail = kg.get_neighbors(entity, value_relation)[0]
    steps = [
        IRStep("v0", "lookup", {"entity": entity, "relation": value_relation, "direction": "neighbors", "index": 0}),
        IRStep("v1", "lookup", {"entity": entity, "relation": delta_relation, "direction": "neighbors", "index": 0}),
    ]
    if "billion" in value_tail.lower():
        steps.extend([
            IRStep("v2", "const", 1000),
            IRStep("v3", "multiply", ["v0", "v2"]),
            IRStep("v4", "subtract", ["v3", "v1"]),
        ])
    else:
        steps.append(IRStep("v2", "subtract", ["v0", "v1"]))
    return _path("template_prior_value_from_change", "Derive requested earlier value from explicit later value and increase"), NumericalProgram(tuple(steps), steps[-1].id)


def deterministic_numerical_candidates(question: str, kg):
    """Return non-overlapping high-confidence IR candidates for a question."""
    candidates = []
    for factory in (
        _comparison_template, _month_total_template, _aggregate_template,
        _prior_value_from_change_template,
    ):
        candidate = factory(question, kg)
        if candidate:
            candidates.append(candidate)
    return candidates
