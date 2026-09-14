import pytest

from src.evaluation.ir_metrics import (
    execute_finqa_gold_program,
    grounding_metrics,
    numerical_ir_metrics,
)
from src.kg.schema import EvidenceRef


def test_executes_finqa_gold_intermediates():
    trace = execute_finqa_gold_program(
        "subtract(193.5, const_100), divide(#0, const_100)"
    )
    assert [item["operator"] for item in trace] == ["subtract", "divide"]
    assert trace[0]["value"] == 93.5
    assert trace[1]["value"] == pytest.approx(0.935)


def test_step_and_operator_accuracy_use_canonical_arithmetic_steps():
    predicted = {"steps": [
        {"id": "v0", "op": "lookup", "arguments": {}},
        {"id": "v1", "op": "const", "arguments": 100},
        {"id": "v2", "op": "subtract", "arguments": ["v0", "v1"]},
        {"id": "v3", "op": "divide", "arguments": ["v2", "v1"]},
    ]}
    metrics = numerical_ir_metrics(
        predicted, {"v0": 193.5, "v1": 100, "v2": 93.5, "v3": 0.935},
        "subtract(193.5, const_100), divide(#0, const_100)", [], None,
    )
    assert metrics["operator_accuracy"] == 1
    assert metrics["step_accuracy"] == 1


def test_grounding_uses_finqa_gold_indices():
    evidence = [
        EvidenceRef("x", "year", "1", "table", "doc", row_index=2),
        EvidenceRef("x", "fact", "y", "text", "doc:text:0"),
    ]
    metrics = grounding_metrics(evidence, {"table_3": "x", "text_0": "y", "text_2": "z"})
    assert metrics["grounding_precision"] == 1
    assert metrics["grounding_recall"] == pytest.approx(2 / 3)


def test_step_metrics_are_null_without_supported_gold_program():
    metrics = numerical_ir_metrics({}, None, None, [], None)
    assert metrics["step_accuracy"] is None
    assert metrics["operator_accuracy"] is None


def test_table_average_matches_equivalent_compressed_gold_macro():
    predicted = {"steps": [
        {"id": "v0", "op": "lookup", "arguments": {}},
        {"id": "v1", "op": "table_average", "arguments": ["v0"]},
    ], "result": "v1"}
    metrics = numerical_ir_metrics(
        predicted, {"v0": [45, 45, 45, 45, 44], "v1": 44.8},
        "multiply(45, const_4), add(#0, 44), divide(#1, const_5)",
        [], None, question="What is the average amount?",
    )
    assert metrics["operator_accuracy"] == 1.0
    assert metrics["step_accuracy"] == 1.0
    assert metrics["strict_operator_accuracy"] == 0.0
    assert metrics["alignment_level"] == "semantic_macro"
    assert metrics["semantic_macro"] == "average"
