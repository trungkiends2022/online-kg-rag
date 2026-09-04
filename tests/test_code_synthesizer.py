from src.execution import code_synthesizer as module
from src.execution.code_synthesizer import CodeSynthesizer
from src.planning.planner import PathStep, ReasoningPath


def test_retries_invalid_code(monkeypatch):
    responses = iter(["result = (", "result = kg.get_sources('date', 'birthDate')"])
    calls = []

    def fake_llm_call(prompt):
        calls.append(prompt)
        return next(responses)

    monkeypatch.setattr(module, "llm_call", fake_llm_call)
    path = ReasoningPath("p1", [PathStep(1, "find person")])

    code = CodeSynthesizer().synthesize(path, "question")

    assert code == "result = kg.get_sources('date', 'birthDate')"
    assert len(calls) == 2
    assert "SyntaxError" in calls[1]
