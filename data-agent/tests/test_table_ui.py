from __future__ import annotations

import unittest

from data_a2a_agent.table_ui import build_bigquery_table_a2ui


class TableUiTests(unittest.TestCase):
    def test_builds_v08_table_surface(self):
        messages = build_bigquery_table_a2ui(
            rows=[
                {"county": "Morgan", "fatal_crashes": 14},
                {"county": "Perry", "fatal_crashes": 30},
            ],
            sql="SELECT county, fatal_crashes FROM `project.dataset.table` LIMIT 2",
        )

        self.assertEqual(list(messages[0]), ["beginRendering"])
        self.assertEqual(list(messages[1]), ["surfaceUpdate"])
        components = messages[1]["surfaceUpdate"]["components"]
        ids = {component["id"] for component in components}
        self.assertIn("header-row", ids)
        self.assertIn("data-row-1", ids)
        self.assertIn("data-row-2-cell-2", ids)
        self.assertIn("sql", ids)

    def test_builds_v09_table_surface(self):
        messages = build_bigquery_table_a2ui(
            rows=[{"county": "Morgan", "fatal_crashes": 14}],
            sql="SELECT county, fatal_crashes FROM `project.dataset.table` LIMIT 1",
            version="v0.9",
            catalog_id="catalog-id",
        )

        self.assertEqual(messages[0]["createSurface"]["catalogId"], "catalog-id")
        components = messages[1]["updateComponents"]["components"]
        ids = {component["id"] for component in components}
        self.assertIn("header-row-cell-1", ids)
        self.assertIn("data-row-1-cell-2", ids)


if __name__ == "__main__":
    unittest.main()
