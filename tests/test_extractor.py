from src.extraction import extractor as extractor_module
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
from src.kg.schema import Provenance, Triple


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

    triples = EntityRelationExtractor(max_output_tokens=777).extract_from_table(
        "revenue", [], use_llm_enrichment=True,
    )

    assert triples[0].head == "Alpha Tech"
    assert triples[0].relation == "revenue"
    assert triples[0].tail == "120"
    assert captured["max_tokens"] == 777
    assert captured["retries"] == 2


def test_table_extraction_splits_large_tables(monkeypatch):
    batches = []

    def fake_llm_call_json(prompt, *, max_tokens, retries):
        batches.append(prompt)
        return [{"head": "row", "relation": "seen", "tail": len(batches)}]

    monkeypatch.setattr(extractor_module, "llm_call_json", fake_llm_call_json)

    triples = EntityRelationExtractor(table_batch_size=2).extract_from_table(
        "table", [{"id": index} for index in range(5)],
        use_llm_enrichment=True,
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


def test_text_batch_extraction_groups_five_passages_into_one_llm_request(monkeypatch):
    calls = []

    def fake_llm_call_json(prompt, *, max_tokens, retries):
        calls.append((prompt, max_tokens, retries))
        return [
            {"source_id": "p0", "head": "Alpha", "relation": "born_in", "tail": "Hanoi"},
            {"source_id": "p4", "head": "Beta", "relation": "born_in", "tail": "Hue"},
        ]

    monkeypatch.setattr(extractor_module, "llm_call_json", fake_llm_call_json)
    triples = EntityRelationExtractor(text_batch_size=5, max_output_tokens=777).extract_from_text_batch([
        {"id": f"p{index}", "text": f"Passage {index}."} for index in range(5)
    ])

    assert len(calls) == 1
    assert calls[0][1:] == (777, 2)
    assert '"source_id": "p0"' in calls[0][0]
    assert {(triple.head, triple.relation, triple.tail, triple.provenance.source_id) for triple in triples} == {
        ("Alpha", "born_in", "Hanoi", "p0"),
        ("Beta", "born_in", "Hue", "p4"),
    }


def test_text_batch_extraction_can_disable_llm_and_keep_deterministic_facts(monkeypatch):
    monkeypatch.setattr(
        extractor_module, "llm_call_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )
    triples = EntityRelationExtractor(use_llm_text_enrichment=False).extract_from_text_batch([{
        "id": "p1",
        "text": "Interest of approximately $9 million per year is payable annually.",
        "context_before": "The net proceeds of the 2025 notes were used for refinancing.",
    }])

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


def test_builder_never_uses_llm_to_enrich_tables(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("table LLM enrichment must be disabled")

    monkeypatch.setattr(extractor_module, "llm_call_json", fail_if_called)
    kg = OnlineKGBuilder(EntityRelationExtractor()).build({
        "table_rows": [{
            "table_name": "companies",
            "rows": [{"Company": "Alpha Tech", "Sector": "Technology"}],
        }],
    })

    assert kg.get_neighbors("Alpha Tech", "sector") == ["Technology"]
    assert kg.summary()["num_text_contexts"] == 0


def test_text_enriches_nodes_and_edges_with_context_after_entity_resolution():
    class FixedTextExtractor(EntityRelationExtractor):
        def extract_from_text(self, passage_id, text, **kwargs):
            return [Triple(
                "alpha tech",
                "founded_in",
                "2001",
                Provenance("text", passage_id, text[:200]),
            )]

    passage = "Alpha Tech was founded in 2001 by two engineers."
    context_before = "The company operates in the technology sector."
    kg = OnlineKGBuilder(FixedTextExtractor()).build({
        "table_rows": [{
            "table_name": "companies",
            "rows": [{"Company": "Alpha Tech", "Sector": "Technology"}],
        }],
        "text_passages": [{
            "id": "company:alpha",
            "text": passage,
            "context_before": context_before,
        }],
    })

    node_contexts = kg.get_node_contexts("Alpha Tech")
    edge_contexts = kg.get_edge_contexts("Alpha Tech", "2001", "founded_in")
    assert node_contexts == [{
        "source_id": "company:alpha",
        "text": passage,
        "context_before": context_before,
    }]
    assert edge_contexts == node_contexts
    assert kg.get_edge_contexts("Alpha Tech", "Technology", "sector") == []
    assert kg.get_evidence("Alpha Tech", "2001", "founded_in")[0].text_context == passage

    trace = kg.to_trace()
    alpha = next(item for item in trace["node_metadata"] if item["id"] == "Alpha Tech")
    founded = next(item for item in trace["edges"] if item["relation"] == "founded_in")
    assert alpha["contexts"] == node_contexts
    assert founded["contexts"] == node_contexts
    assert trace["summary"]["num_contextualized_nodes"] == 2
    assert trace["summary"]["num_contextualized_edges"] == 1


def test_builder_expands_compound_merger_and_links_evidenced_new_entity_alias():
    class MergeExtractor(EntityRelationExtractor):
        def extract_from_text(self, passage_id, text, **kwargs):
            provenance = Provenance("text", passage_id, text[:200])
            return [
                Triple(
                    "Dazu County and Shuangqiao District", "merged_to_form",
                    "new Dazu District", provenance,
                ),
                Triple(
                    "Dazu Rock Carvings", "located_in", "Dazu District", provenance,
                ),
            ]

    passage = "Dazu County and Shuangqiao District were merged to form the new Dazu District."
    kg = OnlineKGBuilder(MergeExtractor()).build({
        "text_passages": [{"id": "dazu", "text": passage}],
    })

    assert "new Dazu District" not in kg.graph
    assert set(kg.get_neighbors("Dazu District", "formed_from")) == {
        "Dazu County", "Shuangqiao District",
    }
    assert kg.get_neighbors("Dazu Rock Carvings", "located_in") == ["Dazu District"]
    merger_edges = [
        edge for edge in kg.to_trace()["edges"]
        if edge["relation"] == "formed_from"
    ]
    assert len(merger_edges) == 2
    assert all(edge["provenance"]["derived_from_compound"] for edge in merger_edges)
    assert all(edge["contexts"][0]["text"] == passage for edge in merger_edges)
    assert any(event["tier"] == "contextual_merger_alias" for event in kg.resolution_log)


def test_builder_preserves_table_cell_hyperlinks_as_grounded_text_bridges():
    class LinkedPassageExtractor(EntityRelationExtractor):
        def extract_from_text(self, passage_id, text, **kwargs):
            return [Triple("Alpha", "born_in", "Hanoi", Provenance("text", passage_id, text))]

    kg = OnlineKGBuilder(LinkedPassageExtractor()).build({
        "table_rows": [{
            "table_name": "people",
            "rows": [{"Name": "Alpha", "Year": "2020"}],
            "cell_links": [{
                "row_index": 0, "column_name": "Name", "cell_value": "Alpha",
                "url": "/wiki/Alpha",
            }],
        }],
        "text_passages": [{"id": "/wiki/Alpha", "text": "Alpha was born in Hanoi."}],
    })

    assert kg.get_neighbors("Alpha", "linked_passage") == ["/wiki/Alpha"]
    records = kg.path_edge_records()
    assert any(
        edge["head"] == "Alpha" and edge["relation"] == "linked_passage"
        and edge["tail"] == "passage:/wiki/Alpha" and edge["structural"]
        for edge in records
    )
    assert any(
        edge["head"] == "passage:/wiki/Alpha" and edge["relation"] == "mentions"
        and edge["tail"] == "Hanoi" and edge["source_type"] == "text"
        for edge in records
    )
