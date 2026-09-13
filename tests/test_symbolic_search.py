from src.evaluation.evaluator import PathEvaluator
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.symbolic_search import SymbolicPathSearcher


def test_symbolic_search_finds_anchored_multihop_path_with_evidence():
    kg = OnlineKG()
    triples = [
        ("Darlington Nagbe", "played_for", "Portland Timbers", "text", "nagbe"),
        ("Darlington Nagbe", "nation", "United States", "table", "crew"),
        ("United States", "most_populous_city", "New York City", "text", "usa"),
        ("Haiti", "most_populous_city", "Port-au-Prince", "text", "haiti"),
        ("United States", "is", "third most populous country in the world", "text", "usa"),
    ]
    for head, relation, tail, source_type, source_id in triples:
        kg.add_triple(Triple(head, relation, tail, Provenance(source_type, source_id)))

    candidates = SymbolicPathSearcher().search(
        "What is the most populous city of the country whose player spent his "
        "first seven seasons with the Portland Timbers?",
        kg,
    )

    assert candidates
    assert candidates[0][2].value == "New York City"
    assert candidates[0][0].steps[0].goal.startswith("Darlington Nagbe")
    assert {item.source_type for item in candidates[0][2].evidence} == {"table", "text"}
    scored = PathEvaluator().evaluate_all(candidates)
    assert scored[0].score > float("-inf")


def test_symbolic_search_requires_a_question_anchor():
    kg = OnlineKG()
    kg.add_triple(Triple(
        "United States", "most_populous_city", "New York City", Provenance("text", "usa")
    ))
    assert SymbolicPathSearcher().search("What is the most populous city?", kg) == []


def test_symbolic_search_accepts_qualified_anchor_name():
    kg = OnlineKG()
    for head, relation, tail in [
        ("Darlington Nagbe", "played_for", "Portland Timbers in MLS"),
        ("Darlington Nagbe", "nation", "United States"),
        ("United States", "most_populous_city", "New York City"),
    ]:
        kg.add_triple(Triple(head, relation, tail, Provenance("text", relation)))
    candidates = SymbolicPathSearcher().search(
        "What is the most populous city of the country whose player was with Portland Timbers?",
        kg,
    )
    assert candidates[0][2].value == "New York City"
