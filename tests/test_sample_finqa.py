from src.sample_finqa import attributes, balanced_sample


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
