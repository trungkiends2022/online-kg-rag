from src.baselines.graph_retrieval import GraphRetrievalNoPathBaseline


def test_graph_prompt_payload_deduplicates_context_by_source_id():
    shared_context = {"source_id": "/wiki/Gaborone", "text": "shared evidence"}
    payload = GraphRetrievalNoPathBaseline._prompt_kg_payload([
        {"edge_id": "0", "head": "Club A", "relation": "city_town", "tail": "Gaborone", "contexts": [shared_context]},
        {"edge_id": "1", "head": "Club B", "relation": "city_town", "tail": "Gaborone", "contexts": [shared_context]},
    ])

    assert payload["contexts_by_source_id"] == {"/wiki/Gaborone": shared_context}
    assert [edge["context_ids"] for edge in payload["edges"]] == [
        ["/wiki/Gaborone"], ["/wiki/Gaborone"],
    ]
    assert all("contexts" not in edge for edge in payload["edges"])


def test_graph_prompt_payload_keeps_structural_table_records():
    payload = GraphRetrievalNoPathBaseline._prompt_kg_payload([
        {
            "edge_id": "record:0", "head": "Gaborone United",
            "relation": "has_record", "tail": "table:League:row:3",
            "source_type": "table", "source_id": "League", "structural": True,
        },
        {
            "edge_id": "record:1", "head": "table:League:row:3",
            "relation": "city_town", "tail": "Gaborone",
            "source_type": "table", "source_id": "League", "structural": True,
        },
    ])

    assert [edge["relation"] for edge in payload["edges"]] == ["has_record", "city_town"]
    assert all(edge["structural"] is True for edge in payload["edges"])
