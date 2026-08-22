from src.evaluation.evaluator import PathEvaluator
from src.execution.sandbox import ExecResult
from src.planning.planner import ReasoningPath, PathStep


def _path(pid, n_steps=1):
    return ReasoningPath(pid, [PathStep(i, f"goal {i}") for i in range(n_steps)])


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
        (_path("p1"), "code1", ExecResult(success=True, value="Alpha Tech", is_empty=False)),
        (_path("p2"), "code2", ExecResult(success=True, value="Alpha Tech", is_empty=False)),
        (_path("p3"), "code3", ExecResult(success=True, value="Beta Foods", is_empty=False)),
    ]
    scored = PathEvaluator().evaluate_all(candidates)
    # 2 path đồng thuận "Alpha Tech" phải xếp trên path lẻ loi "Beta Foods"
    assert scored[0].exec_result.value == "Alpha Tech"
    assert scored[-1].exec_result.value == "Beta Foods"


def test_length_penalty_breaks_ties():
    candidates = [
        (_path("short", n_steps=1), "code", ExecResult(success=True, value="X", is_empty=False)),
        (_path("long", n_steps=4), "code", ExecResult(success=True, value="X", is_empty=False)),
    ]
    scored = PathEvaluator().evaluate_all(candidates)
    assert scored[0].path.path_id == "short"
