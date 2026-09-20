from src.baselines.hybridqa_rag import BaselineConfig, HybridQARAGBaseline
from src.baselines.metrics import exact_match, normalize_answer, semantic_exact_match, token_f1
from src.datasets.schema import DatasetExample


def _example() -> DatasetExample:
    return DatasetExample(
        example_id="q1",
        question="Which club did Alice manage?",
        table_rows=[
            {
                "table_name": "Managers",
                "rows": [
                    {"Manager": "Alice", "Club": "Liverpool"},
                    {"Manager": "Bob", "Club": "Arsenal"},
                ],
            }
        ],
        text_passages=[
            {"id": "irrelevant", "text": "A passage about weather forecasts."},
            {"id": "alice", "text": "Alice managed Liverpool football club."},
            {"id": "history", "text": "The tournament began in 1950."},
        ],
        answer="Liverpool",
    )


def test_metrics_match_hybridqa_normalization():
    assert normalize_answer("The Liverpool!") == "liverpool"
    assert exact_match("Liverpool", "the Liverpool.") == 1.0
    assert token_f1("Liverpool football club", "Liverpool club") == 0.8
    assert exact_match("Morocco", "Moroccan") == 0.0
    assert semantic_exact_match("Morocco", "Moroccan") == 1.0


def test_prompt_keeps_full_oracle_table_and_ranks_only_passages():
    baseline = HybridQARAGBaseline(BaselineConfig(passage_top_k=1))

    prompt, passage_ids, table_truncated = baseline.build_prompt(_example())

    assert '"Manager": "Bob"' in prompt
    assert passage_ids == ["alice"]
    assert "weather forecasts" not in prompt
    assert table_truncated is False


def test_run_uses_one_deterministic_llm_call(monkeypatch):
    calls = []

    class FakeProvider:
        name = "fake"
        model = "fake-model"

    def fake_llm_call(prompt, *, max_tokens, temperature):
        calls.append((prompt, max_tokens, temperature))
        return " Liverpool \n"

    monkeypatch.setattr("src.baselines.hybridqa_rag.get_provider", lambda: FakeProvider())
    monkeypatch.setattr("src.baselines.hybridqa_rag.llm_call", fake_llm_call)
    config = BaselineConfig(max_output_tokens=64, temperature=0.0)

    result = HybridQARAGBaseline(config).run(_example())

    assert result["answer"] == "Liverpool"
    assert result["llm_calls"] == 1
    assert result["provider"] == "fake"
    assert calls[0][1:] == (64, 0.0)
