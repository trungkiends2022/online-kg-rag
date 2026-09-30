from src.baselines.path_text_top_n import PathTextTopNBaseline
from src.baselines.rag_variants import RAGConfig
from src.baselines.shared_context_flat_rag import SharedContextFlatRAGBaseline
from src.datasets.schema import DatasetExample
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.planner import PathStep, ReasoningPath


def _example():
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
        ],
        answer="Liverpool",
        metadata={"dataset": "hybridqa"},
    )


def test_shared_context_flat_rag_uses_two_stage_retrieval(monkeypatch):
    calls, retrieval_calls = [], []
    monkeypatch.setattr(
        "src.baselines.rag_variants.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "m"})(),
    )
    monkeypatch.setattr(
        "src.baselines.rag_variants.llm_call",
        lambda prompt, **kwargs: calls.append(prompt) or "Liverpool",
    )

    def retrieve(*args, **kwargs):
        retrieval_calls.append(kwargs)
        return {
            "table_rows": args[1],
            "text_passages": [args[2][0]],
            "retrieval_trace": {"strategy": "two_stage"},
        }

    monkeypatch.setattr("src.baselines.shared_context_flat_rag.two_stage_retrieve", retrieve)
    result = SharedContextFlatRAGBaseline(RAGConfig(top_k=2)).run(_example())

    assert result["answer"] == "Liverpool"
    assert result["method"] == "flat_rag_shared_context"
    assert result["retrieved_passage_ids"] == ["alice"]
    assert result["retrieval_trace"]["strategy"] == "two_stage"
    assert retrieval_calls == [{"top_k": 2, "second_stage_k": 3, "max_table_rows": None}]
    assert "Retrieved table rows" in calls[0]
    assert "Alice" in calls[0]


def test_path_text_top_n_excludes_auxiliary_graph_edges(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("Alice", "club", "Liverpool", Provenance("table", "Managers")))
    kg.add_triple(Triple("Noise", "unrelated", "Do not include", Provenance("table", "Noise")))

    class Builder:
        def build(self, retrieved):
            return kg

    class Planner:
        def generate_candidates(self, question, graph, n, constraint_context=None):
            return [ReasoningPath(
                "p1",
                [PathStep(1, "Follow Alice to her club")],
                edges=[graph.path_edge_records()[0]],
            )]

    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "m"})(),
    )
    monkeypatch.setattr(
        "src.baselines.online_kg_path_text.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or "Liverpool",
    )
    result = PathTextTopNBaseline(
        RAGConfig(top_k=2), n_paths=1, kg_builder=Builder(), planner=Planner(),
    ).run(_example())

    assert result["answer"] == "Liverpool"
    assert result["method"] == "path_text_top_n"
    assert result["top_n_paths"] == 1
    assert result["path_context_policy"] == "planner_top_n_paths_only"
    assert "Liverpool" in prompts[0]
    assert "Do not include" not in prompts[0]


def test_path_text_marks_low_confidence_answer_as_ungrounded(monkeypatch):
    baseline = PathTextTopNBaseline(RAGConfig(top_k=1), n_paths=1)
    monkeypatch.setattr(baseline, "_answer_match_score", lambda *args: 50.0)
    paths = [{
        "path_id": "p1",
        "edges": [{"edge_id": "edge:1", "head": "Alice", "tail": "Liverpool"}],
    }]

    path_ids, edge_ids, audit = baseline._reverse_ground_answer(
        "What is Alice's club?", "Liverpool", paths,
    )

    assert path_ids == []
    assert edge_ids == []
    assert audit["status"] == "ungrounded"
    assert audit["reason"] == "answer_match_below_grounding_threshold"
