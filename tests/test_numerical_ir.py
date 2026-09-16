import json

import pytest

from src.execution.numerical_ir import (
    NumericalIRExecutor,
    NumericalIRSynthesisError,
    NumericalProgram,
    canonicalize_model_ir,
)
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple


def _kg():
    kg = OnlineKG()
    for triple in [
        Triple("dividend", "2002", "0.55", Provenance("table", "t1", row_index=2, column_name="2002")),
        Triple("dividend", "2001", "0.45", Provenance("table", "t1", row_index=2, column_name="2001")),
    ]:
        kg.add_triple(triple)
    return kg


def test_ir_executes_percentage_and_preserves_lookup_evidence():
    program = NumericalProgram.from_dict({
        "steps": [
            {"id": "v0", "op": "lookup", "arguments": {"entity": "dividend", "relation": "2002", "index": 0}},
            {"id": "v1", "op": "lookup", "arguments": {"entity": "dividend", "relation": "2001", "index": 0}},
            {"id": "v2", "op": "subtract", "arguments": ["v0", "v1"]},
            {"id": "v3", "op": "divide", "arguments": ["v2", "v1"]},
            {"id": "v4", "op": "const", "arguments": 100},
            {"id": "v5", "op": "multiply", "arguments": ["v3", "v4"], "unit": "percent"},
        ],
        "result": "v5",
    })
    result = NumericalIRExecutor().run(program, _kg())
    assert result.success
    assert result.value == pytest.approx(22.2222222)
    assert result.accessed_edges == 2
    assert {item.column_name for item in result.evidence} == {"2001", "2002"}


def test_ir_supports_table_operators_and_financial_number_parsing():
    program = {
        "steps": [
            {"id": "v0", "op": "const", "arguments": ["$1,200", "(200)", 50]},
            {"id": "v1", "op": "table_sum", "arguments": ["v0"]},
            {"id": "v2", "op": "table_average", "arguments": ["v0"]},
        ],
        "result": "v1",
    }
    result = NumericalIRExecutor().run(program, _kg())
    assert result.success and result.value == 1050


def test_ir_counts_inclusive_year_span():
    program = NumericalProgram.from_dict({
        "steps": [
            {"id": "v0", "op": "inclusive_year_count", "arguments": [2017, 2025]},
        ],
        "result": "v0",
    })
    result = NumericalIRExecutor().run(program, _kg())
    assert result.success and result.value == 9


@pytest.mark.parametrize("bad", [
    {"steps": [{"id": "v0", "op": "eval", "arguments": []}], "result": "v0"},
    {"steps": [{"id": "v1", "op": "add", "arguments": ["v0", 1]}], "result": "v1"},
    {"steps": [{"id": "v0", "op": "lookup", "arguments": {"entity": "x"}}], "result": "v0"},
    {"steps": [{"id": "v0", "op": "subtract", "arguments": [1]}], "result": "v0"},
])
def test_ir_rejects_unknown_operator_forward_reference_and_bad_lookup(bad):
    with pytest.raises(ValueError):
        NumericalProgram.from_dict(json.loads(json.dumps(bad)))


def test_synthesis_error_keeps_parse_and_schema_diagnostics():
    error = NumericalIRSynthesisError("bad relation", parse_valid=True, schema_valid=True)
    assert error.parse_valid is True
    assert error.schema_valid is True


def test_canonical_repair_accepts_unambiguous_named_binary_operands():
    raw = {"steps": [
        {"id": "v0", "op": "const", "arguments": 10},
        {"id": "v1", "op": "const", "arguments": 4},
        {"id": "v2", "op": "subtract", "arguments": {"minuend": "v0", "subtrahend": "v1"}},
    ], "result": "v2"}
    repaired, count = canonicalize_model_ir(raw)
    program = NumericalProgram.from_dict(repaired, repair_count=count)
    assert program.steps[-1].arguments == ["v0", "v1"]
    assert program.repair_count == 1


def test_ir_supports_hitab_selection_range_filter_and_count():
    program = NumericalProgram.from_dict({
        "steps": [
            {"id": "v0", "op": "const", "arguments": 4},
            {"id": "v1", "op": "const", "arguments": -2},
            {"id": "v2", "op": "const", "arguments": 9},
            {"id": "v3", "op": "argmax", "arguments": [
                {"label": "A", "value": "v0"}, {"label": "B", "value": "v2"}]},
            {"id": "v4", "op": "topk_argmin", "arguments": {"items": [
                {"label": "A", "value": "v0"}, {"label": "B", "value": "v1"},
                {"label": "C", "value": "v2"}], "k": 2}},
            {"id": "v5", "op": "filter_less", "arguments": {"items": [
                {"label": "A", "value": "v0"}, {"label": "B", "value": "v1"}],
                "threshold": 0}},
            {"id": "v6", "op": "count", "arguments": "v5"},
            {"id": "v7", "op": "range", "arguments": ["v0", "v1", "v2"]},
        ],
        "result": "v7",
    })
    result = NumericalIRExecutor().run(program, _kg())
    assert result.success
    assert result.step_values["v3"] == "B"
    assert result.step_values["v4"] == ["B", "A"]
    assert result.step_values["v6"] == 1
    assert result.value == [9.0, -2.0]


def test_ir_supports_less_and_negate():
    program = NumericalProgram.from_dict({
        "steps": [
            {"id": "v0", "op": "less", "arguments": [2, 3]},
            {"id": "v1", "op": "negate", "arguments": [5]},
        ],
        "result": "v1",
    })
    result = NumericalIRExecutor().run(program, _kg())
    assert result.success and result.step_values["v0"] is True and result.value == -5
