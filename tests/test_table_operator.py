"""Tests for TableOperatorPlanner and TableWitness integration."""

import unittest

from src.planning.table_operator import (
    TableOperatorPlanner,
    TableWitness,
    clean_number,
    is_summary_row,
    row_primary_entity,
)
from src.planning.entity_anchor import anchor_question
from src.retrieval.coarse_retrieval import two_stage_retrieve
from src.kg.builder import OnlineKGBuilder
from src.extraction.extractor import EntityRelationExtractor
from src.planning.grounded_paths import GroundedPathPlanner


class TestTableOperator(unittest.TestCase):
    def setUp(self):
        self.planner = TableOperatorPlanner()
        self.sample_table = {
            "table_name": "Football Money League",
            "rows": [
                {"Rank": "1", "Club": "Real Madrid", "Revenue": "292.2", "Country": "Spain"},
                {"Rank": "16", "Club": "Hamburger SV", "Revenue": "101.8", "Country": "Germany"},
                {"Rank": "17", "Club": "Manchester City", "Revenue": "89.4", "Country": "England"},
                {"Rank": "18", "Club": "Rangers", "Revenue": "88.5", "Country": "Scotland"},
                {"Rank": "-", "Club": "Total", "Revenue": "1000.0", "Country": "All"},
            ],
            "cell_links": [
                {"row_index": 2, "column_name": "Club", "cell_value": "Manchester City", "url": "/wiki/Manchester_City_F.C."},
                {"row_index": 3, "column_name": "Club", "cell_value": "Rangers", "url": "/wiki/Rangers_F.C."},
            ],
        }

    def test_clean_number(self):
        self.assertEqual(clean_number("101.8"), 101.8)
        self.assertEqual(clean_number("$89.4M"), 89.4)
        self.assertEqual(clean_number("€ 88.5 [1]"), 88.5)
        self.assertEqual(clean_number("1,200.5"), 1200.5)
        self.assertIsNone(clean_number("N/A"))
        self.assertIsNone(clean_number("-"))

    def test_summary_row_and_primary_entity(self):
        self.assertTrue(is_summary_row({"Club": "Total", "Revenue": "1000"}))
        self.assertFalse(is_summary_row({"Club": "Arsenal", "Revenue": "200"}))
        self.assertEqual(row_primary_entity(self.sample_table["rows"][2]), "Manchester City")

    def test_numeric_interval_operator(self):
        q = "Which group purchased the football club whose 2007 revenue was less than 101.8 but more than 88.5 ?"
        witnesses = self.planner.plan_numeric_interval(q, self.sample_table)
        self.assertEqual(len(witnesses), 1)
        w = witnesses[0]
        self.assertEqual(w.operator, "numeric_interval")
        self.assertEqual(w.row_indices, (2,))
        self.assertEqual(w.bridge_entities, ("Manchester City",))
        self.assertEqual(w.hyperlinks, ("/wiki/Manchester_City_F.C.",))
        self.assertAlmostEqual(w.intermediate_values["matched_value"], 89.4)

    def test_frequency_and_latest_operator(self):
        table = {
            "table_name": "Sevens Grand Prix",
            "rows": [
                {"Team": "Portugal", "Runners-up": "1 ( 2012 )"},
                {"Team": "France", "Runners-up": "7 ( 2003 , 2007 , 2010 , 2019 )"},
                {"Team": "Russia", "Runners-up": "2 ( 2005 , 2006 )"},
                {"Team": "Total", "Runners-up": "10"},
            ],
            "cell_links": [
                {"row_index": 1, "column_name": "Runners-up", "cell_value": "7 ( 2003 , 2007 , 2010 , 2019 )", "url": "/wiki/2003_Championship"},
                {"row_index": 1, "column_name": "Runners-up", "cell_value": "7 ( 2003 , 2007 , 2010 , 2019 )", "url": "/wiki/2019_Grand_Prix"},
            ],
        }
        q = "Where was the 2nd leg held during the most recent championships that the team to finish runner-up most frequently finished as runner-up ?"
        witnesses = self.planner.plan_frequency_and_latest(q, table)
        self.assertEqual(len(witnesses), 1)
        w = witnesses[0]
        self.assertEqual(w.operator, "frequency_and_latest")
        self.assertEqual(w.row_indices, (1,))
        self.assertIn("France", w.bridge_entities)
        self.assertEqual(w.hyperlinks, ("/wiki/2019_Grand_Prix",))
        self.assertEqual(w.intermediate_values["max_count"], 7)

    def test_extremum_argmax_operator(self):
        table = {
            "table_name": "High Buildings",
            "rows": [
                {"Building": "Tower A", "Height ( m )": "200"},
                {"Building": "Tower B", "Height ( m )": "450"},
                {"Building": "Tower C", "Height ( m )": "310"},
            ],
            "cell_links": [
                {"row_index": 1, "column_name": "Building", "cell_value": "Tower B", "url": "/wiki/Tower_B"},
            ],
        }
        q = "What is the name of the tallest building?"
        witnesses = self.planner.plan_extremum(q, table)
        self.assertEqual(len(witnesses), 1)
        w = witnesses[0]
        self.assertEqual(w.operator, "argmax")
        self.assertEqual(w.row_indices, (1,))
        self.assertEqual(w.bridge_entities, ("Tower B",))
        self.assertEqual(w.hyperlinks, ("/wiki/Tower_B",))

    def test_text_condition_operator(self):
        table = {
            "table_name": "Acts",
            "rows": [
                {"Artist": "Deep Purple", "Album": "Machine Head"},
                {"Artist": "Adele", "Album": "21"},
            ],
            "cell_links": [
                {"row_index": 0, "column_name": "Album", "cell_value": "Machine Head", "url": "/wiki/Machine_Head"},
                {"row_index": 1, "column_name": "Artist", "cell_value": "Adele", "url": "/wiki/Adele"},
                {"row_index": 1, "column_name": "Album", "cell_value": "21", "url": "/wiki/21"},
            ],
        }
        passages = [
            {"id": "/wiki/Machine_Head", "text": "Machine Head was released in 1972."},
            {"id": "/wiki/Adele", "text": "Adele signed a recording contract with XL Recordings. Best female singer."},
            {"id": "/wiki/21", "text": "21 spent the most weeks on the billboard 200 of any album."},
        ]
        q = "What was the name of the label that signed the artist that released an album that spent the most weeks on the Billboard 200 of any album by a woman ?"
        witnesses = self.planner.plan_text_condition(q, table, passages)
        self.assertEqual(len(witnesses), 1)
        w = witnesses[0]
        self.assertEqual(w.operator, "text_condition")
        self.assertEqual(w.row_indices, (1,))
        self.assertIn("Adele", w.bridge_entities)
        self.assertIn("/wiki/Adele", w.hyperlinks)

    def test_end_to_end_grounded_path_slot_reservation(self):
        q = "Which group purchased the football club whose 2007 revenue was less than 101.8 but more than 88.5 ?"
        passages = [
            {"id": "/wiki/Manchester_City_F.C.", "text": "Manchester City F.C. was purchased in 2008 by Abu Dhabi United Group."},
            {"id": "/wiki/Rangers_F.C.", "text": "Rangers F.C. is in Glasgow."},
        ]
        retrieved = two_stage_retrieve(q, [self.sample_table], passages, [])
        self.assertTrue(bool(retrieved["retrieval_trace"].get("table_witnesses")))

        builder = OnlineKGBuilder(EntityRelationExtractor(use_llm_text_enrichment=False))
        kg = builder.build(retrieved)
        planner = GroundedPathPlanner()
        paths = planner.generate_candidates(q, kg, n=5, constraint_context=retrieved["retrieval_trace"])
        self.assertGreater(len(paths), 0)
        # Top path must be grounded in Manchester City / witness row 2
        top_path = paths[0]
        path_text = " ".join(f"{s.goal}" for s in top_path.steps)
        self.assertIn("Manchester City", path_text)


if __name__ == "__main__":
    unittest.main()
