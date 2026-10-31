from src.extraction.rule_text_triples import extract_rule_text_triples


def test_extracts_situated_between_as_graph_nodes_and_edges():
    text = (
        "Gaborone City, is situated between Kgale and Oodi Hills, "
        "near the confluence of two rivers."
    )

    triples = extract_rule_text_triples("/wiki/Gaborone", text)
    facts = {(triple.head, triple.relation, triple.tail) for triple in triples}

    assert ("Gaborone", "situated_between", "Kgale and Oodi Hills") in facts
    assert ("Gaborone", "situated_between_landmark", "Kgale") in facts
    assert ("Gaborone", "situated_between_landmark", "Oodi Hills") in facts
    assert all(triple.provenance.source_group == "rule_text" for triple in triples)


