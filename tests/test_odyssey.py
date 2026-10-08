from src.baselines.odyssey import OdysseyBaseline, OdysseyConfig
from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample


def _example():
    return DatasetExample(
        example_id="odyssey-q1",
        question="What nationality was the driver in position 4?",
        table_rows=[{
            "table_name": "Grand Prix",
            "rows": [{"Pos": "4", "Driver": "Jenson Button", "Team": "BAR"}],
            "cell_links": [{"row_index": 0, "column_name": "Driver", "cell_value": "Jenson Button", "url": "/wiki/Jenson_Button"}],
        }],
        text_passages=[{"id": "Jenson_Button", "text": "Jenson Button is a British racing driver."}],
        answer="British",
        metadata={"dataset": "hybridqa"},
    )


def test_odyssey_runs_question_analysis_then_hopwise_reader(monkeypatch):
    calls = []
    monkeypatch.setattr("src.baselines.odyssey.get_provider", lambda: type("Provider", (), {"name": "fake", "model": "fake"})())
    responses = iter([
        '{"entities": ["position 4", "nationality"]}',
        '{"headers": ["Pos", "Driver"]}',
        '{"mapping": {"position 4": ["Pos"], "nationality": ["Others"]}}',
        "Final Answer: British\nRelevant Passages: []",
    ])
    monkeypatch.setattr("src.baselines.odyssey.llm_call", lambda prompt, **kwargs: calls.append(prompt) or next(responses))

    result = OdysseyBaseline(RAGConfig(max_context_chars=10_000), OdysseyConfig(max_hops=3)).run(_example())

    assert result["answer"] == "British"
    assert result["method"] == "odyssey"
    assert len(calls) == 4
    assert result["odyssey_question_analysis"]["selected_headers"] == ["Pos", "Driver"]
    assert result["odyssey_graph"]["document_count"] == 1
    assert result["odyssey_full_context_fallback"] is False


def test_odyssey_falls_back_to_full_context_after_none(monkeypatch):
    monkeypatch.setattr("src.baselines.odyssey.get_provider", lambda: type("Provider", (), {"name": "fake", "model": "fake"})())
    responses = iter([
        '{"entities": ["position 4"]}',
        '{"headers": ["Pos", "Driver"]}',
        '{"mapping": {"position 4": ["Pos"]}}',
        "Final Answer: None\nRelevant Passages: [\"Jenson_Button\"]",
        "Final Answer: British\nRelevant Passages: []",
    ])
    monkeypatch.setattr("src.baselines.odyssey.llm_call", lambda *args, **kwargs: next(responses))

    result = OdysseyBaseline(RAGConfig(max_context_chars=10_000), OdysseyConfig(max_hops=1)).run(_example())

    assert result["answer"] == "British"
    assert result["odyssey_full_context_fallback"] is True
    assert result["odyssey_reader_attempts"][-1]["fallback"] is True
