from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.grounded_paths import GroundedPathPlanner


def test_grounded_paths_use_existing_edges_and_reward_cross_modal_chain():
    kg = OnlineKG()
    kg.add_triple(Triple(
        "Rank 2", "player", "Walter Payton", Provenance("table", "rushing")
    ))
    kg.add_triple(Triple(
        "Walter Payton", "full_name", "Walter Jerry Payton",
        Provenance("text", "walter"),
    ))

    paths = GroundedPathPlanner(max_hops=2).generate_candidates(
        "What is the full name of the player at rank 2?", kg, n=3,
    )

    assert paths
    best = paths[0]
    assert best.edges
    assert best.score_components["grounded_edges"] == 1.0
    assert best.score_components["cross_modal_completeness"] == 1.5
    available = {edge["edge_id"] for edge in kg.path_edge_records()}
    assert {edge["edge_id"] for edge in best.edges} <= available


def test_grounded_row_bundle_keeps_year_and_value_in_one_path():
    kg = OnlineKG()
    kg.register_table_structure(
        "revenue",
        [{"Company": "A", "Year": "2022", "Revenue": "10M"}],
    )

    paths = GroundedPathPlanner(max_hops=3).generate_candidates(
        "What was A revenue in 2022?", kg, n=5,
    )

    row_paths = [
        path for path in paths
        if path.score_components.get("row_context") == 1.0
    ]
    assert row_paths
    relations = {edge["relation"] for edge in row_paths[0].edges}
    assert {"has_record", "year", "revenue"} <= relations


def test_grounded_path_ranking_uses_attached_text_context():
    kg = OnlineKG()
    kg.register_passage(
        "award:1",
        "The Zephyr award was presented to the winning architect.",
    )
    kg.add_triple(Triple(
        "Candidate A", "received", "Prize",
        Provenance("text", "award:1"),
    ))
    kg.add_triple(Triple(
        "Candidate B", "received", "Other",
        Provenance("table", "candidates"),
    ))

    paths = GroundedPathPlanner(max_hops=1).generate_candidates(
        "Who received the Zephyr award?", kg, n=2,
    )

    assert paths[0].edges[0]["source_id"] == "award:1"
    assert paths[0].score_components["text_context_match"] > 0
