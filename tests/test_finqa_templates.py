from src.execution.finqa_templates import deterministic_numerical_candidates
from src.execution.numerical_ir import NumericalIRExecutor
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.pipeline import OnlineKGPipeline


def _add(kg, head, relation, tail):
    kg.add_triple(Triple(head, relation, tail, Provenance("table", "t")))


def _run(question, kg):
    candidates = deterministic_numerical_candidates(question, kg)
    assert candidates
    return NumericalIRExecutor().run(candidates[0][1], kg)


def test_average_template_uses_exact_named_row_and_years():
    kg = OnlineKG()
    _add(kg, "capital expenditures on a gaap basis", "2013_period", "1747.8")
    _add(kg, "capital expenditures on a gaap basis", "2012_period", "2559.8")
    _add(kg, "capital expenditures on a gaap basis", "2011_period", "1365.9")
    _add(kg, "capital expenditures on a non-gaap basis", "2013_period", "1996.7")
    _add(kg, "capital expenditures on a non-gaap basis", "2012_period", "2084.9")
    _add(kg, "capital expenditures on a non-gaap basis", "2011_period", "2232.8")
    result = _run("Considering the years 2011-2013, what is the average capital expenditure on a gaap basis?", kg)
    assert result.success
    assert result.value == 1891.1666666666667


def test_total_template_does_not_drop_total_column_or_rescale_unit():
    kg = OnlineKG()
    for relation, value in [
        ("payments_due_total", "20147"), ("payments_due_less_than_1_year", "6932"),
        ("payments_due_1_3_years", "9105"), ("payments_due_3_5_years", "2592"),
        ("payments_due_more_than_5_years", "1518"),
    ]:
        _add(kg, "total obligations", relation, value)
    result = _run("What are the total contractual commitments, in millions?", kg)
    assert result.success
    assert result.value == 40294.0


def test_month_total_template_includes_all_rows_through_target_month():
    kg = OnlineKG()
    for entity, date, proceeds in [
        ("cilcorp", "January 2003", "495"), ("ecogen", "January 2003", "59"),
        ("mountainview", "March 2003", "30"), ("kelvin", "March 2003", "29"),
        ("songas", "April 2003", "94"),
    ]:
        _add(kg, entity, "date_completed", date)
        _add(kg, entity, "sales_proceeds_in_millions", proceeds)
    result = _run("For the three months ended March 2003 what were the total sales proceeds in millions?", kg)
    assert result.success
    assert result.value == 613.0


def test_outperform_template_compares_latest_shared_date():
    kg = OnlineKG()
    _add(kg, "ball corporation", "12_31_05", "100.00")
    _add(kg, "ball corporation", "12_31_10", "178.93")
    _add(kg, "dj containers and packaging index", "12_31_05", "100.00")
    _add(kg, "dj containers and packaging index", "12_31_10", "123.56")
    result = _run("Did the five year total return on Ball Corporation outperform the DJ containers and packaging index?", kg)
    assert result.success and result.value is True


def test_prior_value_template_normalizes_billion_before_subtraction():
    kg = OnlineKG()
    _add(kg, "operating income", "value_2014", "$1.6 billion")
    _add(kg, "operating income", "increase_from_2013_to_2014", "$108 million")
    result = _run("What is the total operating income in 2013, in millions?", kg)
    assert result.success and result.value == 1492.0


def test_pipeline_keeps_template_when_optional_planner_fails(monkeypatch):
    kg = OnlineKG()
    _add(kg, "total obligations", "payments_due_total", "20147")
    _add(kg, "total obligations", "payments_due_less_than_1_year", "6932")
    _add(kg, "total obligations", "payments_due_1_3_years", "9105")
    _add(kg, "total obligations", "payments_due_3_5_years", "2592")
    _add(kg, "total obligations", "payments_due_more_than_5_years", "1518")
    pipeline = OnlineKGPipeline(execution_mode="numerical_ir")
    monkeypatch.setattr(pipeline.kg_builder, "build", lambda _: kg)
    monkeypatch.setattr(pipeline.planner, "generate_candidates", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider down")))

    result = pipeline.run("What are the total contractual commitments, in millions?", [], [], [], n_paths=3)
    assert result["executed_value"] == 40294.0
