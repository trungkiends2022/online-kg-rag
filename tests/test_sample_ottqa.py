import json

from src.sample_ottqa import select_eligible_records, split_sample, uniform_sample


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_ottqa_sampler_excludes_hybrid_overlap_and_is_reproducible(tmp_path):
    tables = tmp_path / "tables"
    passages = tmp_path / "passages"
    tables.mkdir()
    passages.mkdir()
    for table_id in ("t1", "t2", "t3"):
        _write_json(tables / f"{table_id}.json", {"header": ["Name"], "data": [["A"]]})
        _write_json(passages / f"{table_id}.json", {"A": ["linked passage"]})
    records = [
        {"question_id": "q1", "table_id": "t1", "answer-text": "A"},
        {"question_id": "q2", "table_id": "t2", "answer-text": "B"},
        {"question_id": "q3", "table_id": "t3", "answer-text": "C"},
        {"question_id": "q4", "table_id": "missing", "answer-text": "D"},
    ]

    eligible, skipped = select_eligible_records(
        records, tables_dir=tables, passages_dir=passages, excluded_question_ids={"q2"}
    )
    first = uniform_sample(eligible, size=2, seed=2027)
    second = uniform_sample(eligible, size=2, seed=2027)

    assert {item["question_id"] for item in eligible} == {"q1", "q3"}
    assert skipped == {"overlaps_hybridqa_dev": 1, "missing_table_file": 1}
    assert [item["question_id"] for item in first] == [item["question_id"] for item in second]


def test_ottqa_sampler_splits_fixed_batches_with_short_final_batch():
    records = [{"question_id": str(index)} for index in range(5)]

    shards = split_sample(records, shard_size=2)

    assert [len(shard) for shard in shards] == [2, 2, 1]
    assert [item["question_id"] for shard in shards for item in shard] == [
        "0", "1", "2", "3", "4"
    ]


def test_ottqa_sampler_requires_answer_node(tmp_path):
    tables = tmp_path / "tables"
    passages = tmp_path / "passages"
    tables.mkdir()
    passages.mkdir()
    for table_id in ("t1", "t2"):
        _write_json(tables / f"{table_id}.json", {"header": ["Name"], "data": [["A"]]})
        _write_json(passages / f"{table_id}.json", {"A": ["linked passage"]})
    records = [
        {"question_id": "q1", "table_id": "t1", "answer-text": "A", "answer-node": [["A", "/wiki/A", "A", "passage"]]},
        {"question_id": "q2", "table_id": "t2", "answer-text": "B", "answer-node": []},
    ]

    eligible, skipped = select_eligible_records(
        records, tables_dir=tables, passages_dir=passages, require_answer_node=True
    )

    assert {item["question_id"] for item in eligible} == {"q1"}
    assert skipped == {"missing_answer_node": 1}


def test_load_question_ids_multiple_paths(tmp_path):
    from src.sample_ottqa import load_question_ids
    f1 = tmp_path / "f1.json"
    f2 = tmp_path / "f2.json"
    _write_json(f1, [{"question_id": "q1"}, {"question_id": "q2"}])
    _write_json(f2, [{"question_id": "q2"}, {"question_id": "q3"}])
    ids = load_question_ids([f1, f2])
    assert ids == {"q1", "q2", "q3"}

