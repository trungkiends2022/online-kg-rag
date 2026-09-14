from src.evaluation import answer_synthesizer as module
from src.evaluation.answer_synthesizer import AnswerSynthesizer
from src.evaluation.evaluator import ScoredPath
from src.execution.sandbox import ExecResult
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.planner import PathStep, ReasoningPath


def test_prefers_short_entity_alias_in_answer_prompt(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("Liverpool", "country", "England", Provenance("table", "t1")))
    kg.add_triple(Triple("Liverpool Football Club", "won", "six European Cups", Provenance("text", "p1")))
    kg.merge_entities("Liverpool Football Club", ["Liverpool"], tier="structural")
    best = ScoredPath(
        ReasoningPath("p1", [PathStep(1, "find club")]),
        "result = ...",
        ExecResult(True, "Liverpool Football Club", is_empty=False),
        8.5,
    )
    prompts = []
    monkeypatch.setattr(module, "llm_call", lambda prompt: prompts.append(prompt) or "Liverpool")

    answer = AnswerSynthesizer().synthesize("Which club?", best, kg)

    assert answer == "Liverpool"
    assert "Tên hiển thị ưu tiên (alias tương đương, nếu có): Liverpool" in prompts[0]


def test_numeric_result_bypasses_verbalizer_and_preserves_sign(monkeypatch):
    best = ScoredPath(
        ReasoningPath("p1", [PathStep(1, "subtract")]),
        '{"op":"subtract"}',
        ExecResult(True, -2143.0, is_empty=False),
        3.25,
    )
    monkeypatch.setattr(
        module, "llm_call", lambda _prompt: (_ for _ in ()).throw(AssertionError("must not call LLM"))
    )
    assert AnswerSynthesizer().synthesize("How much did it decline?", best, OnlineKG()) == "-2143.0"
