from src.baselines.hybridqa_rag import BaselineConfig, HybridQARAGBaseline
from src.baselines.metrics import (
    exact_match,
    normalize_answer,
    semantic_exact_match,
    token_f1,
)
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


def test_metrics_normalize_plural_surface_forms():
    assert normalize_answer("The clubs, cities and wolves!") == "club city and wolf"
    assert exact_match("Gaborone United", "Gaborone United.") == 1.0
    assert exact_match("football club", "football clubs") == 1.0


def test_metrics_normalize_unicode_hyphens_and_parenthetical_unit_conversions():
    assert exact_match("1991-92", "1991\u201192") == 1.0
    assert exact_match("806 km", "806 km (≈ 501 mi)") == 1.0
    assert normalize_answer("151 square miles (392 km²)") == "151 square mile"


def test_semantic_em_applies_explicit_rule_based_equivalences_only():
    assert exact_match("seven", "7") == 0.0
    assert semantic_exact_match("seven", "7") == 1.0
    assert semantic_exact_match(
        "fourteen", "14 years", question="How many years did the driver race?",
    ) == 1.0
    assert semantic_exact_match(
        "21 seasons", "21", question="How many seasons did the player compete?",
    ) == 1.0
    assert semantic_exact_match("21 seasons", "21") == 0.0
    assert semantic_exact_match("a quarter", "about a quarter of its population") == 1.0
    assert semantic_exact_match("PyeongChang", "Pyeongchang County") == 1.0
    assert semantic_exact_match("southern", "southern coast") == 1.0
    assert semantic_exact_match("Equatoguinean", "Equatoguinean Premier League") == 1.0
    assert semantic_exact_match(
        "Lancaster University and a campus of the University of Cumbria",
        "Lancaster University and the University of Cumbria",
    ) == 1.0


def test_prompt_keeps_full_oracle_table_and_ranks_only_passages():
    baseline = HybridQARAGBaseline(BaselineConfig(passage_top_k=1))

    prompt, passage_ids, table_truncated, retrieval_trace = baseline.build_prompt(_example())

    assert '"Manager": "Bob"' in prompt
    assert passage_ids[0] == "alice"
    assert retrieval_trace["passage_reranker_query"] == "question_plus_selected_rows"
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
    assert "non-empty, single-line answer span" in calls[0][0]


def test_direct_rag_retries_empty_and_placeholder_answers():
    assert HybridQARAGBaseline._needs_retry("")
    assert HybridQARAGBaseline._needs_retry("N/A")
    assert HybridQARAGBaseline._needs_retry("unknown")
    assert not HybridQARAGBaseline._needs_retry("Liverpool")
