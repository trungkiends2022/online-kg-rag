from src.evaluation.evaluator import PathEvaluator
from src.execution.sandbox import ExecResult
from src.kg.schema import EvidenceRef
from src.planning.planner import ReasoningPath, PathStep


def _path(pid, n_steps=1):
    return ReasoningPath(pid, [PathStep(i, f"goal {i}") for i in range(n_steps)])


def _evidence(value, source_type="text", source_id="s1"):
    return (EvidenceRef("subject", "answer", str(value), source_type, source_id),)


def _result(value, source_type="text", source_id="s1"):
    evidence = _evidence(value, source_type, source_id)
    return ExecResult(True, value, is_empty=False, evidence=evidence, accessed_edges=1)


def test_errored_path_gets_neg_inf():
    candidates = [(_path("p1"), "bad code", ExecResult(success=False, error="SyntaxError"))]
    scored = PathEvaluator().evaluate_all(candidates)
    assert scored[0].score == float("-inf")


def test_empty_result_gets_neg_inf():
    candidates = [(_path("p1"), "code", ExecResult(success=True, value=[], is_empty=True))]
    scored = PathEvaluator().evaluate_all(candidates)
    assert scored[0].score == float("-inf")


def test_self_consistency_rewards_agreement():
    candidates = [
        (_path("p1"), "code1", _result("Alpha Tech", source_id="s1")),
        (_path("p2"), "code2", _result("Alpha Tech", source_id="s2")),
        (_path("p3"), "code3", _result("Beta Foods", source_id="s3")),
    ]
    scored = PathEvaluator().evaluate_all(candidates)
    # 2 path đồng thuận "Alpha Tech" phải xếp trên path lẻ loi "Beta Foods"
    assert scored[0].exec_result.value == "Alpha Tech"
    assert scored[-1].exec_result.value == "Beta Foods"


def test_length_penalty_breaks_ties():
    candidates = [
        (_path("short", n_steps=1), "code", _result("X")),
        (_path("long", n_steps=4), "code", _result("X")),
    ]
    scored = PathEvaluator().evaluate_all(candidates)
    assert scored[0].path.path_id == "short"


def test_ungrounded_output_is_rejected():
    result = ExecResult(success=True, value="invented", is_empty=False)
    scored = PathEvaluator().evaluate_all([(_path("p1"), "code", result)])
    assert scored[0].score == float("-inf")
    assert "ungrounded" in scored[0].reasons[0]


def test_derived_numeric_output_keeps_grounded_lineage():
    evidence = (
        EvidenceRef("Revenue", "value", "10", "table", "financials"),
        EvidenceRef("Cost", "value", "4", "table", "financials"),
    )
    result = ExecResult(True, 6, evidence=evidence, accessed_edges=2)
    scored = PathEvaluator().evaluate_all([(_path("calculation"), "code", result)])
    assert scored[0].score > float("-inf")
    assert "grounding_mode=derived_numeric" in scored[0].reasons


def test_table_and_text_evidence_beats_three_paths_from_one_source():
    wrong = _result("Arsenal", "text", "same-passage")
    table = _result("Liverpool", "table", "league-table")
    text = _result("Liverpool", "text", "liverpool-passage")
    candidates = [
        (_path("wrong-1"), "code", wrong),
        (_path("wrong-2"), "code", wrong),
        (_path("wrong-3"), "code", wrong),
        (_path("right-table"), "code", table),
        (_path("right-text"), "code", text),
    ]

    scored = PathEvaluator().evaluate_all(candidates)

    assert scored[0].exec_result.value == "Liverpool"
    assert "provenance_types=table,text" in scored[0].reasons
    assert "cross_modality_bonus=+1.50" in scored[0].reasons


def test_text_only_beats_web_only_with_same_other_signals():
    candidates = [
        (_path("text"), "code", _result("Text answer", "text", "p1")),
        (_path("web"), "code", _result("Web answer", "web", "w1")),
    ]
    scored = PathEvaluator().evaluate_all(candidates)
    assert scored[0].path.path_id == "text"
