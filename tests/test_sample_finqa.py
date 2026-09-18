from src.sample_finqa import (
    CORE_ARITHMETIC_OPERATORS,
    attributes,
    balanced_sample,
    disjoint_balanced_shards,
    filter_records,
    program_operators,
)


def _item(index, program, evidence):
    return {"id": str(index), "qa": {"program": program, "gold_inds": evidence}}


def test_balanced_sample_is_reproducible_and_covers_operators():
    records = [
        _item(0, "add(1, 2)", {"table_1": "x"}),
        _item(1, "subtract(2, 1)", {"text_1": "x"}),
        _item(2, "divide(2, 1), multiply(#0, 100)", {"table_1": "x", "text_1": "y"}),
        _item(3, "add(3, 4)", {"table_2": "x"}),
        _item(4, "subtract(4, 2)", {"text_2": "x"}),
    ]

    first = balanced_sample(records, size=3, seed=2027)
    second = balanced_sample(records, size=3, seed=2027)

    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert {attributes(item)[0] for item in first} == {"add", "subtract", "multiply"}


def test_filter_records_selects_exactly_two_core_arithmetic_steps():
    records = [
        _item(0, "subtract(5, 2), divide(#0, 2)", {"table_1": "x"}),
        _item(1, "add(1, 2)", {"table_1": "x"}),
        _item(2, "table_sum(table), divide(#0, 2)", {"table_1": "x"}),
        _item(3, "multiply(3, 4), add(#0, 1)", {"text_1": "x"}),
    ]

    selected = filter_records(
        records, exact_steps=2, allowed_operators=CORE_ARITHMETIC_OPERATORS
    )

    assert [item["id"] for item in selected] == ["0", "3"]
    assert program_operators(selected[0]) == ("subtract", "divide")


def test_disjoint_balanced_shards_do_not_repeat_records():
    records = [
        _item(index, "subtract(5, 2), divide(#0, 2)", {"table_1": "x"})
        for index in range(6)
    ]
    shards = disjoint_balanced_shards(records, shard_size=2, shards=3, seed=2027)
    ids = [item["id"] for shard in shards for item in shard]
    assert len(ids) == len(set(ids)) == 6
