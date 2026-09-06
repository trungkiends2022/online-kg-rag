from src.execution import code_synthesizer as module
from src.execution.code_synthesizer import CodeSynthesizer
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.planner import PathStep, ReasoningPath


def test_retries_invalid_code(monkeypatch):
    responses = iter(["result = (", "result = kg.get_sources('date', 'birthDate')"])
    calls = []

    def fake_llm_call(prompt, *, max_tokens):
        calls.append((prompt, max_tokens))
        return next(responses)

    monkeypatch.setattr(module, "llm_call", fake_llm_call)
    path = ReasoningPath("p1", [PathStep(1, "find person")])

    code = CodeSynthesizer().synthesize(path, "question")

    assert code == "result = kg.get_sources('date', 'birthDate')"
    assert len(calls) == 2
    assert all(max_tokens == 4096 for _, max_tokens in calls)
    assert "SyntaxError" in calls[1][0]


def _kg():
    kg = OnlineKG()
    kg.add_triple(Triple("Liverpool Football Club", "won", "six European Cups", Provenance("text", "p1")))
    kg.add_triple(Triple("Liverpool Football Club", "country", "England", Provenance("table", "t1")))
    return kg


def test_retries_hard_coded_result_and_grounds_prompt(monkeypatch):
    responses = iter([
        'result = "Liverpool Football Club"',
        'result = kg.get_sources("six European Cups", "won")[0]',
    ])
    prompts = []
    monkeypatch.setattr(module, "llm_call", lambda prompt, **_kwargs: prompts.append(prompt) or next(responses))

    code = CodeSynthesizer().synthesize(
        ReasoningPath("p1", [PathStep(1, "find club")]), "Which club?", _kg()
    )

    assert code == 'result = kg.get_sources("six European Cups", "won")[0]'
    assert "hard-coded string result" in prompts[1]
    assert "Relations hợp lệ: ['country', 'won']" in prompts[0]


def test_retries_invalid_api_keyword(monkeypatch):
    responses = iter([
        'result = kg.get_neighbors(obj="six European Cups", relation="won")',
        'result = kg.get_sources("six European Cups", relation="won")',
    ])
    prompts = []
    monkeypatch.setattr(module, "llm_call", lambda prompt, **_kwargs: prompts.append(prompt) or next(responses))

    CodeSynthesizer().synthesize(
        ReasoningPath("p2", [PathStep(1, "reverse lookup")]), "Which club?", _kg()
    )

    assert "invalid keyword" in prompts[1]


def test_retries_relation_not_present_in_kg(monkeypatch):
    responses = iter([
        'result = kg.get_neighbors("Liverpool Football Club", "champions_league_titles")',
        'result = kg.get_neighbors("Liverpool Football Club", "won")',
    ])
    prompts = []
    monkeypatch.setattr(module, "llm_call", lambda prompt, **_kwargs: prompts.append(prompt) or next(responses))

    CodeSynthesizer().synthesize(
        ReasoningPath("p3", [PathStep(1, "find wins")]), "Which club?", _kg()
    )

    assert "relation not present in KG" in prompts[1]


def test_retries_wrong_edge_direction(monkeypatch):
    responses = iter([
        'result = kg.get_neighbors("six European Cups", "won")',
        'result = kg.get_sources("six European Cups", "won")',
    ])
    prompts = []
    monkeypatch.setattr(module, "llm_call", lambda prompt, **_kwargs: prompts.append(prompt) or next(responses))

    CodeSynthesizer().synthesize(
        ReasoningPath("p4", [PathStep(1, "find source")]), "Which club?", _kg()
    )

    assert "wrong edge direction" in prompts[1]
    assert "use get_sources" in prompts[1]


def test_retries_indirect_hard_coded_result(monkeypatch):
    responses = iter([
        'club = "Liverpool Football Club"\nresult = club',
        'result = kg.get_sources("six European Cups", "won")[0]',
    ])
    prompts = []
    monkeypatch.setattr(module, "llm_call", lambda prompt, **_kwargs: prompts.append(prompt) or next(responses))

    CodeSynthesizer().synthesize(
        ReasoningPath("p5", [PathStep(1, "find club")]), "Which club?", _kg()
    )

    assert "through a variable" in prompts[1]
