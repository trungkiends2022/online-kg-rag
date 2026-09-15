from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.operation_intent import infer_operation_intent


def _kg_with_relation(relation):
    kg = OnlineKG()
    kg.add_triple(Triple("ontario", relation, "35.4", Provenance("table", "t")))
    return kg


def test_combined_existing_percentages_prefers_direct_add_without_gold_label():
    intent = infer_operation_intent(
        "What was the proportion in British Columbia and Ontario combined?",
        _kg_with_relation("sector_percentage"),
    )
    assert intent["source"] == "question_and_kg_schema"
    assert intent["preferred_operators"] == ["add"]
    assert "add those displayed percentage cells directly" in intent["constraints"][0]


def test_combined_counts_does_not_force_percentage_addition():
    intent = infer_operation_intent(
        "What was the combined proportion?", _kg_with_relation("worker_count")
    )
    assert intent["preferred_operators"] == []


def test_temporal_change_preserves_signed_subtraction():
    intent = infer_operation_intent(
        "How much did it decline from FY 2012 to FY 2013?", _kg_with_relation("value")
    )
    assert "subtract" in intent["preferred_operators"]
    assert any("B minus A" in rule for rule in intent["constraints"])


def test_outperform_prefers_grounded_boolean_comparison():
    intent = infer_operation_intent(
        "Did Ball outperform the packaging index?", _kg_with_relation("five_year_return")
    )
    assert "greater" in intent["preferred_operators"]
    assert "add" not in intent["preferred_operators"]


def test_total_name_alone_does_not_force_addition():
    intent = infer_operation_intent(
        "What is total operating income in 2013?", _kg_with_relation("operating_income")
    )
    assert "add" not in intent["preferred_operators"]
