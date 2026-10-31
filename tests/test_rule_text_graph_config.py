from src.baselines.graph_retrieval import GraphRetrievalNoPathBaseline
from src.baselines.online_kg_path_text import OnlineKGPathTextBaseline
from src.baselines.rag_variants import RAGConfig
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder


def test_rule_text_triples_default_to_enabled_for_both_kg_baselines():
    config = RAGConfig()

    assert config.use_rule_text_triples is True
    assert GraphRetrievalNoPathBaseline(config).kg_builder.extractor.use_rule_text_triples is True
    assert OnlineKGPathTextBaseline(config).kg_builder.extractor.use_rule_text_triples is True


def test_rule_text_triples_merge_into_semantic_nodes_and_path_edges():
    kg = OnlineKGBuilder(EntityRelationExtractor(
        use_llm_text_enrichment=False,
        use_rule_text_triples=True,
    )).build({
        "text_passages": [{
            "id": "gaborone",
            "text": "Gaborone City is situated between Kgale and Oodi Hills.",
        }],
    })

    assert {"Gaborone", "Kgale", "Oodi Hills"} <= set(kg.graph.nodes)
    records = kg.path_edge_records()
    assert any(
        record["head"] == "Gaborone"
        and record["relation"] == "situated_between_landmark"
        and record["tail"] == "Oodi Hills"
        and record["source_group"] == "rule_text"
        for record in records
    )


def test_graph_no_path_view_keeps_semantic_text_and_table_structure_together():
    kg = OnlineKGBuilder(EntityRelationExtractor(
        use_llm_text_enrichment=False,
        use_rule_text_triples=True,
    )).build({
        "table_rows": [{
            "table_name": "Botswana Premier League",
            "rows": [{"Club": "Gaborone United", "City / Town": "Gaborone"}],
            "row_indices": [3],
        }],
        "text_passages": [{
            "id": "/wiki/Gaborone",
            "text": "Gaborone City is situated between Kgale and Oodi Hills.",
        }],
    })

    records = kg.path_edge_records()
    cell_id = "table:Botswana Premier League:row:3:cell:City / Town"
    assert any(
        edge["head"] == "Gaborone"
        and edge["relation"] == "situated_between_landmark"
        and edge["tail"] == "Oodi Hills"
        and edge["structural"] is False
        and edge["source_group"] == "rule_text"
        for edge in records
    )
    assert any(
        edge["head"] == "table:Botswana Premier League:row:3"
        and edge["relation"] == "city_town"
        and edge["tail"] == cell_id
        and edge["structural"] is True
        for edge in records
    )
    payload = GraphRetrievalNoPathBaseline._prompt_kg_payload(records)
    assert "/wiki/Gaborone" in payload["contexts_by_source_id"]
