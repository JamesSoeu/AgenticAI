from __future__ import annotations

import unittest

from orchestrator_router.routing import extract_text, route_request


class RouterTests(unittest.TestCase):
    def test_extract_text_from_a2a_payload(self):
        payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {"kind": "text", "text": "Show bridges in county 001 on a map"}
                    ]
                }
            },
        }

        self.assertEqual(extract_text(payload), "Show bridges in county 001 on a map")

    def test_routes_pdf_question_to_data_agent(self):
        route = route_request(
            "Search the bridge inspection PDF manual for inspection responsibility"
        )

        self.assertEqual(route, "data")

    def test_routes_map_question_to_map_agent(self):
        route = route_request("Show bridges in county 001 on a Google map")

        self.assertEqual(route, "map")

    def test_routes_bridge_structure_lookup_to_map_agent(self):
        route = route_request("Find bridge structure 1234567")

        self.assertEqual(route, "map")

    def test_routes_crash_question_to_data_agent(self):
        route = route_request("Show crash counts by severity for the latest year")

        self.assertEqual(route, "data")


if __name__ == "__main__":
    unittest.main()
