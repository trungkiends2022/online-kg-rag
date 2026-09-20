from src.retrieval.coarse_retrieval import two_stage_retrieve


def test_second_stage_recovers_explicit_annual_interest_fact():
    passages = [
        {"id": "p1", "text": "Long-term borrowings had a carrying value."},
        {"id": "p2", "text": "The notes may be redeemed prior to maturity."},
        {"id": "p3", "text": "Interest of $9 million per year is payable annually."},
    ]
    result = two_stage_retrieve(
        "What is the interest from 2017 to 2025 as a percentage of borrowings?",
        [{"table_name": "borrowings", "rows": [{"maturity amount": "4938"}]}],
        passages,
        [],
        top_k=1,
        second_stage_k=1,
    )

    assert "p3" in [item["id"] for item in result["text_passages"]]
    assert result["retrieval_trace"]["stage2_budget"] == 1


def test_second_stage_zero_budget_preserves_first_stage_size():
    passages = [
        {"id": "p1", "text": "interest and borrowings"},
        {"id": "p2", "text": "interest payable annually per year"},
    ]
    result = two_stage_retrieve(
        "interest as a percentage", [], passages, [], top_k=1, second_stage_k=0
    )

    assert len(result["text_passages"]) == 1


def test_entity_anchor_recovers_passage_for_table_derived_bridge_entity():
    passages = [
        {"id": "p1", "text": "Barry Sanders was an NFL player."},
        {"id": "p2", "text": "Jim Brown was an NFL player."},
        {"id": "walter", "text": "Walter Jerry Payton was an NFL player."},
    ]
    result = two_stage_retrieve(
        "What is the middle name of the player with the second most rushing yards?",
        [{"table_name": "rushing", "rows": [
            {"Rank": "1", "Player": "Emmitt Smith"},
            {"Rank": "2", "Player": "Walter Payton"},
        ]}],
        passages,
        [],
        top_k=1,
        second_stage_k=1,
    )

    assert result["retrieval_trace"]["entity_anchor"]["bridge_entities"] == ("Walter Payton",)
    assert "walter" in [item["id"] for item in result["text_passages"]]
