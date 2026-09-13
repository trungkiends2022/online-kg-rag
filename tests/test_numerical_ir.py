import json

import pytest

from src.execution.numerical_ir import (
    NumericalIRExecutor,
    NumericalIRSynthesisError,
    NumericalProgram,
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
