import json

from src.sample_hybridqa import (
    cross_modal_proxy,
    select_table_text_records,
    split_sample,
    stratified_shards,
)


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_select_table_text_records_can_require_answer_node(tmp_path):
    tables = tmp_path / "tables"
    passages = tmp_path / "passages"
    tables.mkdir()
    passages.mkdir()
    for table_id in ("t1", "t2"):
        _write_json(tables / f"{table_id}.json", {"header": ["Name"], "data": [["A"]]})
        _write_json(passages / f"{table_id}.json", {"A": ["A", "passage"]})
    records = [
        {"question_id": "q1", "table_id": "t1", "answer-text": "A", "answer-node": [["A"]]},
        {"question_id": "q2", "table_id": "t2", "answer-text": "A"},
    ]

    selected = select_table_text_records(
        records, tables_dir=tables, passages_dir=passages, require_answer_node=True
    )

    assert [item["question_id"] for item in selected] == ["q1"]


def test_split_sample_keeps_all_records_and_allows_short_final_shard():
    records = [{"question_id": str(index)} for index in range(5)]

    shards = split_sample(records, shard_size=2)

    assert [len(shard) for shard in shards] == [2, 2, 1]
    assert [item["question_id"] for shard in shards for item in shard] == [
        "0", "1", "2", "3", "4"
    ]


def test_cross_modal_proxy_detects_hidden_table_bridge():
    item = {
        "question": "When was the vendor founded?",
        "answer-node": [["Microsoft Corporation", [1, 2], "/wiki/Microsoft", "passage"]],
    }

    assert cross_modal_proxy(item) == "table_to_text_likely"


def test_stratified_shards_balance_reasoning_attributes_and_are_reproducible():
    records = []
    for index in range(12):
        source = "passage" if index < 6 else "table"
        records.append({
            "question_id": str(index),
            "question": "Who was second?" if index % 2 else "Who won?",
            "answer-text": "answer",
            "answer-node": [[
                f"hidden entity {index}", [index, 0],
                f"/wiki/{index}" if source == "passage" else None,
                source,
            ]],
        })

    first = stratified_shards(records, shard_size=4, seed=2027)
    second = stratified_shards(records, shard_size=4, seed=2027)

    assert [len(shard) for shard in first] == [4, 4, 4]
    assert [[item["question_id"] for item in shard] for shard in first] == [
        [item["question_id"] for item in shard] for shard in second
    ]
    for shard in first:
        assert sum(item["answer-node"][0][-1] == "passage" for item in shard) == 2
