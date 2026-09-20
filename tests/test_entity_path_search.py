from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning.symbolic_search import SymbolicPathSearcher


def test_symbolic_middle_name_path_uses_table_and_text_evidence():
    kg = OnlineKG()
    kg.add_triple(Triple("2", "player", "Walter Payton", Provenance("table", "rushing")))
    kg.add_triple(Triple("Walter Payton", "full_name", "Walter Jerry Payton", Provenance("text", "walter")))

    paths = SymbolicPathSearcher().search(
        "What is the middle name of the player with the second most rushing yards?", kg
    )

    path, _, result = paths[0]
    assert path.path_id == "symbolic_middle_name"
    assert result.value == "Jerry"
    assert {item.source_type for item in result.evidence} == {"table", "text"}
