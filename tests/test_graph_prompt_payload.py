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
