from src.extraction import extractor as extractor_module
from src.extraction.extractor import EntityRelationExtractor


def test_unbounded_text_batch_uses_one_llm_request(monkeypatch):
    calls = []

    def fake_llm_call_json(prompt, *, max_tokens, retries):
        calls.append(prompt)
        return []

    monkeypatch.setattr(extractor_module, "llm_call_json", fake_llm_call_json)
    passages = [
        {"id": f"p{index}", "text": f"Passage {index}."}
        for index in range(6)
    ]

    EntityRelationExtractor(text_batch_size=None).extract_from_text_batch(passages)

    assert len(calls) == 1
