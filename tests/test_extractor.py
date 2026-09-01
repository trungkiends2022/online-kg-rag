from src.extraction import extractor as extractor_module
from src.extraction.extractor import EntityRelationExtractor


def test_table_extraction_normalizes_scalar_values_to_strings(monkeypatch):
    captured = {}

    def fake_llm_call_json(prompt, *, max_tokens):
        captured["max_tokens"] = max_tokens
        return [{"head": "Alpha Tech", "relation": "revenue", "tail": 120}]

    monkeypatch.setattr(
        extractor_module,
        "llm_call_json",
        fake_llm_call_json,
    )

    triples = EntityRelationExtractor().extract_from_table("revenue", [])

    assert triples[0].head == "Alpha Tech"
    assert triples[0].relation == "revenue"
    assert triples[0].tail == "120"
    assert captured["max_tokens"] == 4096


def test_table_extraction_splits_large_tables(monkeypatch):
    batches = []

    def fake_llm_call_json(prompt, *, max_tokens):
        batches.append(prompt)
        return [{"head": "row", "relation": "seen", "tail": len(batches)}]

    monkeypatch.setattr(extractor_module, "llm_call_json", fake_llm_call_json)

    triples = EntityRelationExtractor(table_batch_size=2).extract_from_table(
        "table", [{"id": index} for index in range(5)]
    )

    assert len(batches) == 3
    assert [triple.tail for triple in triples] == ["1", "2", "3"]
