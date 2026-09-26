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


def test_table_literal_constraint_prioritizes_candidate_passages_and_does_not_misread_whose():
    passages = [
        {"id": "angles", "text": "English was named after the Angles."},
        {"id": "belgium", "text": "Belgium is a country in Europe."},
        {"id": "latvia", "text": "Latvia is a Baltic country."},
        {"id": "lithuania", "text": "Lithuania is commonly linked to the Lietava river."},
    ]
    question = (
        "Which jurisdiction whose standard tax rate was 21 % is mostly credited "
        "to be named after a river?"
    )
    result = two_stage_retrieve(
        question,
        [{"table_name": "tax", "rows": [
            {"Jurisdiction": "Belgium", "Rate Standard": "21%"},
            {"Jurisdiction": "Latvia", "Rate Standard": "21%"},
            {"Jurisdiction": "Lithuania", "Rate Standard": "21%"},
        ]}],
        passages,
        [],
        top_k=1,
        second_stage_k=1,
    )

    trace = result["retrieval_trace"]
    assert trace["entity_anchor"]["target_attribute"] is None
    assert trace["table_constraints"] == [{
        "column": "Rate Standard",
        "value": "21 %",
        "entity_column": "Jurisdiction",
        "candidates": ("Belgium", "Latvia", "Lithuania"),
        "enforce_output": True,
    }]
    assert "lithuania" in [item["id"] for item in result["text_passages"]]


def test_short_table_retrieval_keeps_every_row_and_original_index():
    result = two_stage_retrieve(
        "What is the middle name of the player with the second most rushing yards?",
        [{"table_name": "rushing", "rows": [
            {"Rank": "1", "Player": "Emmitt Smith"},
            {"Rank": "2", "Player": "Walter Payton"},
            {"Rank": "3", "Player": "Barry Sanders"},
        ]}],
        [],
        [],
        top_k=1,
        second_stage_k=0,
    )

    group = result["table_rows"][0]
    assert group["rows"] == [
        {"Rank": "1", "Player": "Emmitt Smith"},
        {"Rank": "2", "Player": "Walter Payton"},
        {"Rank": "3", "Player": "Barry Sanders"},
    ]
    assert group["row_indices"] == [0, 1, 2]
    assert result["retrieval_trace"]["selected_table_rows"] == 3


def test_short_table_retrieval_preserves_all_cell_links():
    result = two_stage_retrieve(
        "Where was Alpha born?",
        [{
            "table_name": "people",
            "rows": [{"Name": "Alpha"}, {"Name": "Beta"}],
            "cell_links": [
                {"row_index": 0, "column_name": "Name", "cell_value": "Alpha", "url": "/wiki/Alpha"},
                {"row_index": 1, "column_name": "Name", "cell_value": "Beta", "url": "/wiki/Beta"},
            ],
        }],
        [], [], top_k=1, second_stage_k=0,
    )

    assert result["table_rows"][0]["cell_links"] == [
        {"row_index": 0, "column_name": "Name", "cell_value": "Alpha", "url": "/wiki/Alpha"},
        {"row_index": 1, "column_name": "Name", "cell_value": "Beta", "url": "/wiki/Beta"},
    ]


def test_long_table_retrieval_filters_cell_links_to_selected_rows():
    rows = [{"Name": f"Person {index}"} for index in range(30)]
    rows.append({"Name": "Target Person"})
    result = two_stage_retrieve(
        "Where was Target Person born?",
        [{
            "table_name": "people",
            "rows": rows,
            "cell_links": [
                {"row_index": 0, "column_name": "Name", "cell_value": "Person 0", "url": "/wiki/Person_0"},
                {"row_index": 30, "column_name": "Name", "cell_value": "Target Person", "url": "/wiki/Target"},
            ],
        }],
        [], [], top_k=1, second_stage_k=0,
    )

    group = result["table_rows"][0]
    assert group["row_indices"] == [30]
    assert group["cell_links"] == [{
        "row_index": 30,
        "column_name": "Name",
        "cell_value": "Target Person",
        "url": "/wiki/Target",
    }]
