from __future__ import annotations

import unittest

from data_a2a_agent.config import BigQueryTable
from data_a2a_agent.tools import _assert_blob_allowed, _validate_select_sql


ALLOWED = (
    BigQueryTable(
        alias="bridge",
        project="project",
        dataset="bridge_inventory",
        table="bridge",
    ),
)


class ToolTests(unittest.TestCase):
    def test_validate_select_sql_accepts_allowed_table(self):
        sql = _validate_select_sql(
            "SELECT * FROM `project.bridge_inventory.bridge`", ALLOWED
        )

        self.assertEqual(sql, "SELECT * FROM `project.bridge_inventory.bridge`")

    def test_validate_select_sql_rejects_mutation(self):
        with self.assertRaisesRegex(ValueError, "Only SELECT"):
            _validate_select_sql(
                "DELETE FROM `project.bridge_inventory.bridge` WHERE true", ALLOWED
            )

    def test_validate_select_sql_rejects_unconfigured_table(self):
        with self.assertRaisesRegex(ValueError, "non-configured"):
            _validate_select_sql(
                "SELECT * FROM `project.bridge_inventory.crash`", ALLOWED
            )

    def test_assert_blob_allowed_limits_prefix(self):
        _assert_blob_allowed("enterprise", "enterprise/policies/security.txt")

        with self.assertRaisesRegex(ValueError, "configured prefix"):
            _assert_blob_allowed("enterprise", "other/security.txt")

if __name__ == "__main__":
    unittest.main()
