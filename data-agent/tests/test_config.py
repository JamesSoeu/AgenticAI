from __future__ import annotations

import unittest

from data_a2a_agent.config import _parse_bigquery_tables


class ConfigTests(unittest.TestCase):
    def test_parse_bigquery_tables_with_aliases(self):
        tables = _parse_bigquery_tables(
            "project_a.bridge_inventory.bridge,bridge_inventory.crash",
            "bridge,crash",
            "default_project",
        )

        self.assertEqual([table.alias for table in tables], ["bridge", "crash"])
        self.assertEqual(
            [table.full_id for table in tables],
            [
                "project_a.bridge_inventory.bridge",
                "default_project.bridge_inventory.crash",
            ],
        )

    def test_parse_bigquery_tables_rejects_alias_length_mismatch(self):
        with self.assertRaisesRegex(ValueError, "must match"):
            _parse_bigquery_tables(
                "project.dataset.table,project.dataset.other", "one", "project"
            )

    def test_parse_bigquery_tables_requires_project(self):
        with self.assertRaisesRegex(ValueError, "needs a project"):
            _parse_bigquery_tables("dataset.table", "", "")

if __name__ == "__main__":
    unittest.main()
