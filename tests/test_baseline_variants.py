from src.baselines.metrics import (
    extract_last_number,
    finqa_execution_match,
    finqa_ratio_percentage_match,
)
from src.baselines.path_consistency import PathConsistencyEvaluator
from src.baselines.rag_variants import (
    FlatTableBM25Baseline,
    OracleEvidenceBaseline,
    RAGConfig,
    flatten_documents,
)
from src.baselines.online_kg_path_text import OnlineKGPathTextBaseline
from src.datasets.schema import DatasetExample
from src.execution.sandbox import ExecResult
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.planner import PathStep, ReasoningPath


def _example(metadata=None):
    return DatasetExample(
        example_id="q1",
        question="What is Alice's club?",
        table_rows=[{
            "table_name": "Managers",
            "rows": [
                {"Name": "Alice", "Club": "Liverpool"},
                {"Name": "Bob", "Club": "Arsenal"},
            ],
        }],
        text_passages=[
            {"id": "alice", "text": "Alice managed Liverpool."},
            {"id": "weather", "text": "Rain is expected tomorrow."},
            {"id": "history", "text": "The event began in 1900."},
        ],
        answer="Liverpool",
        metadata=metadata or {"dataset": "hybridqa"},
    )


def test_flatten_documents_preserves_row_and_source_identity():
    documents = flatten_documents(_example())

    assert documents[0]["id"] == "table:Managers:row:0"
    assert "Name is Alice" in documents[0]["text"]
    assert documents[0]["source_type"] == "table"
    assert any(item["id"] == "text:alice" for item in documents)


def test_flat_table_baseline_retrieves_and_calls_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "src.baselines.rag_variants.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "m"})(),
    )
    monkeypatch.setattr(
        "src.baselines.rag_variants.llm_call",
        lambda prompt, **kwargs: calls.append(prompt) or "Liverpool",
    )

    result = FlatTableBM25Baseline(RAGConfig(top_k=2)).run(_example())

    assert result["answer"] == "Liverpool"
    assert result["llm_calls"] == 1
    assert len(calls) == 1
    assert any("Alice" in item for item in calls)


def test_online_kg_path_text_answers_without_program_execution(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("Alice", "club", "Liverpool", Provenance("table", "Managers")))

    class Builder:
        def build(self, retrieved):
            return kg

    class Planner:
        def generate_candidates(self, question, graph, n, constraint_context=None):
            return [ReasoningPath("p1", [PathStep(1, "Follow Alice --club--> answer")])]

    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "m"})(),
    )
    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or "Liverpool",
    )
    baseline = OnlineKGPathTextBaseline(
        RAGConfig(top_k=2), n_paths=1, kg_builder=Builder(), planner=Planner()
    )
    result = baseline.run(_example())
    assert result["answer"] == "Liverpool"
    assert result["execution_mode"] == "path_text"
    assert result["code_generated"] is False
    assert result["program_executed"] is False
    assert "Alice --club--> answer" in prompts[0]


def test_online_kg_path_text_ranks_relevant_late_edge_and_keeps_json_context(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("Noise", "unrelated", "Ignore", Provenance("text", "noise")))
    kg.add_triple(Triple("Lithuania", "named_after", "Lietava river", Provenance("text", "lt")))

    class Builder:
        def build(self, retrieved):
            return kg

    class Planner:
        def generate_candidates(self, question, graph, n, constraint_context=None):
            return [ReasoningPath("p1", [PathStep(1, "Find Lithuania named after river")])]

    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "m"})(),
    )
    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or "Lithuania",
    )
    baseline = OnlineKGPathTextBaseline(
        RAGConfig(top_k=1, max_context_chars=600), n_paths=1,
        kg_builder=Builder(), planner=Planner(),
    )
    example = _example()
    example.question = "Which jurisdiction is named after a river?"
    result = baseline.run(example)

    assert result["answer"] == "Lithuania"
    assert '"kg_edges"' in prompts[0]
    assert "Lietava river" in prompts[0]


def test_online_kg_path_text_canonicalizes_resolved_entity_alias(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple(
        "Opponent", "home_arena", "Vazgen Sargsyan Republican Stadium",
        Provenance("text", "match"),
    ))
    kg.entity_aliases["Republican Stadium"] = "Vazgen Sargsyan Republican Stadium"

    class Builder:
        def build(self, retrieved):
            return kg

    class Planner:
        def generate_candidates(self, question, graph, n, constraint_context=None):
            return [ReasoningPath("p1", [PathStep(1, "Find home arena")])]

    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "m"})(),
    )
    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.llm_call",
        lambda prompt, **kwargs: "Vazgen Sargsyan Republican Stadium",
    )
    result = OnlineKGPathTextBaseline(
        RAGConfig(top_k=1), n_paths=1, kg_builder=Builder(), planner=Planner()
    ).run(_example())

    assert result["answer"] == "Republican Stadium"


def test_online_kg_path_text_rejects_empty_grounded_path_set(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("Alice", "club", "Liverpool", Provenance("table", "Managers")))

    class Builder:
        def build(self, retrieved):
            return kg

    class Planner:
        def generate_candidates(self, question, graph, n, constraint_context=None):
            return []

    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.llm_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("answer model must not be called without a grounded path")
        ),
    )
    result = OnlineKGPathTextBaseline(
        RAGConfig(top_k=1), n_paths=1, kg_builder=Builder(), planner=Planner()
    ).run(_example())

    assert result["answer"] is None
    assert result["reasoning_paths"] == []
    assert "No grounded text path" in result["error"]


def test_oracle_evidence_uses_finqa_gold_facts_only(monkeypatch):
    example = _example({
        "dataset": "finqa",
        "gold_evidence": {"table_3": "American Express volume is 637."},
    })
    captured = []
    monkeypatch.setattr(
        "src.baselines.rag_variants.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "m"})(),
    )
    monkeypatch.setattr(
        "src.baselines.rag_variants.llm_call",
        lambda prompt, **kwargs: captured.append(prompt) or "127.4",
    )

    result = OracleEvidenceBaseline().run(example)

    assert result["oracle_document_ids"] == ["gold:table_3"]
    assert "American Express volume is 637" in captured[0]
    assert "Liverpool" not in captured[0]


def test_oracle_evidence_requires_annotations():
    try:
        OracleEvidenceBaseline().run(_example())
    except ValueError as exc:
        assert "No oracle evidence" in str(exc)
    else:
        raise AssertionError("missing oracle annotation should fail")


def test_path_consistency_votes_without_requiring_evidence():
    def path(name):
        return ReasoningPath(name, [PathStep(1, "answer")])

    candidates = [
        (path("a"), "", ExecResult(True, "Liverpool")),
        (path("b"), "", ExecResult(True, "Liverpool")),
        (path("c"), "", ExecResult(True, "Arsenal")),
    ]

    scored = PathConsistencyEvaluator().evaluate_all(
        candidates,
        constraint_policy={"allowed_output_values": ["Liverpool"]},
        question="What is the nationality?",
    )

    assert scored[0].exec_result.value == "Liverpool"
    assert scored[0].score == 2.0
    assert scored[0].reasons == ["path_votes=2"]


def test_finqa_numeric_answer_metrics():
    assert extract_last_number("The answer is 127.40.") == 127.4
    assert finqa_execution_match(127.4, "The result is 127.40000") == 1.0
    assert finqa_execution_match(127.4, "127.5") == 0.0
    assert finqa_execution_match(1.11111, "1.111111111") == 1.0
    assert finqa_execution_match(1_000_000, "1000001") == 0.0
    assert finqa_execution_match("yes", "yes") == 1.0
    assert finqa_execution_match("no", "yes") == 0.0
    assert finqa_execution_match("yes", True) == 1.0
    assert finqa_execution_match("no", False) == 1.0
    assert finqa_ratio_percentage_match(0.21651, 21.650534895568008) == 1.0
    assert finqa_ratio_percentage_match(21.65053, 0.2165053) == 1.0
    assert finqa_ratio_percentage_match(0.21651, 18.0) == 0.0
