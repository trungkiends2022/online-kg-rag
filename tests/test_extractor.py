from src.extraction import extractor as extractor_module
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder


def test_table_extraction_normalizes_scalar_values_to_strings(monkeypatch):
    captured = {}

    def fake_llm_call_json(prompt, *, max_tokens, retries):
        captured["max_tokens"] = max_tokens
        captured["retries"] = retries
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
    assert captured["retries"] == 2


def test_table_extraction_splits_large_tables(monkeypatch):
    batches = []

    def fake_llm_call_json(prompt, *, max_tokens, retries):
        batches.append(prompt)
        return [{"head": "row", "relation": "seen", "tail": len(batches)}]

    monkeypatch.setattr(extractor_module, "llm_call_json", fake_llm_call_json)

    triples = EntityRelationExtractor(table_batch_size=2).extract_from_table(
        "table", [{"id": index} for index in range(5)]
    )

    assert len(batches) == 3
    assert [triple.tail for triple in triples] == ["1", "2", "3"]


def test_table_extraction_preserves_qualified_cell_relations(monkeypatch):
    monkeypatch.setattr(extractor_module, "llm_call_json", lambda *args, **kwargs: [])
    triples = EntityRelationExtractor().extract_from_table(
        "dividends",
        [{"Quarter Ended": "March 31", "2002_High": "26.50", "2002_Dividend": ".450"}],
    )
    facts = {(triple.head, triple.relation, triple.tail) for triple in triples}
    assert ("March 31", "2002_High", "26.50") in facts
    assert ("March 31", "2002_Dividend", ".450") in facts
    dividend = next(t for t in triples if t.relation == "2002_Dividend")
    assert dividend.provenance.row_index == 0
    assert dividend.provenance.column_name == "2002_Dividend"
    assert dividend.provenance.header_path == ("2002", "Dividend")


def test_text_extraction_scopes_annual_interest_to_context_note(monkeypatch):
    monkeypatch.setattr(extractor_module, "llm_call_json", lambda *args, **kwargs: [])
    triples = EntityRelationExtractor().extract_from_text(
        "doc:text:20",
        "Interest of approximately $9 million per year is payable annually.",
        context_before="The net proceeds of the 2025 notes were used for refinancing.",
    )

    assert ("2025 notes", "annual_interest_amount", "$9 million per year") in {
        (triple.head, triple.relation, triple.tail) for triple in triples
    }


def test_text_extraction_preserves_later_value_and_prior_year_change(monkeypatch):
    monkeypatch.setattr(extractor_module, "llm_call_json", lambda *args, **kwargs: [])
    triples = EntityRelationExtractor().extract_from_text(
        "doc:text:1",
        "Operating income increased $108 million, or 7%, from 2013 to $1.6 billion in 2014.",
    )
    facts = {(triple.head, triple.relation, triple.tail) for triple in triples}
    assert ("Operating income", "value_2014", "$1.6 billion") in facts
    assert ("Operating income", "increase_from_2013_to_2014", "$108 million") in facts


def test_deterministic_text_fact_survives_malformed_llm_response(monkeypatch):
    monkeypatch.setattr(extractor_module, "llm_call_json", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad JSON")))
    triples = EntityRelationExtractor().extract_from_text(
        "doc:text:1",
        "Operating income increased $108 million from 2013 to $1.6 billion in 2014.",
    )
    assert any(triple.relation == "value_2014" for triple in triples)


def test_builder_skips_one_malformed_passage_instead_of_aborting():
    class FailingExtractor(EntityRelationExtractor):
        def extract_from_table(self, *args, **kwargs):
            return []

        def extract_from_text(self, passage_id, text, **kwargs):
            if passage_id == "bad":
                raise ValueError("malformed JSON")
            return [self._triple(passage_id)]

        @staticmethod
        def _triple(passage_id):
            from src.kg.schema import Provenance, Triple
            return Triple("interest", "amount", "9", Provenance("text", passage_id))

    kg = OnlineKGBuilder(FailingExtractor()).build({
        "text_passages": [
            {"id": "bad", "text": "broken"},
            {"id": "good", "text": "interest is 9"},
        ]
    })

    assert kg.get_neighbors("interest", "amount") == ["9"]
    assert kg.summary()["num_extraction_errors"] == 1
