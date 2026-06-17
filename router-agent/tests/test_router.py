from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator_router.card import build_agent_card
from orchestrator_router.classifier import classify_route, parse_classifier_response
from orchestrator_router.config import RouterSettings
from orchestrator_router.routing import extract_text


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

    def test_parse_classifier_response_for_data_agent(self):
        decision = parse_classifier_response(
            '{"route":"data","confidence":0.93,"reason":"PDF manual question"}'
        )

        self.assertEqual(decision.route, "data")
        self.assertEqual(decision.confidence, 0.93)
        self.assertEqual(decision.source, "llm")

    def test_parse_classifier_response_for_map_agent_with_markdown_fence(self):
        decision = parse_classifier_response(
            '```json\n{"route":"map","confidence":0.88,"reason":"map display"}\n```'
        )

        self.assertEqual(decision.route, "map")
        self.assertEqual(decision.confidence, 0.88)

    def test_parse_classifier_response_clamps_confidence(self):
        decision = parse_classifier_response(
            '{"route":"data","confidence":2.5,"reason":"table count"}'
        )

        self.assertEqual(decision.confidence, 1.0)

    def test_low_confidence_classifier_response_uses_default_route(self):
        with patch(
            "orchestrator_router.classifier._call_gemini_classifier",
            return_value='{"route":"map","confidence":0.4,"reason":"ambiguous"}',
        ):
            decision = classify_route("Tell me about bridge 1234567", _settings())

        self.assertEqual(decision.route, "data")
        self.assertEqual(decision.source, "fallback")

    def test_agent_card_has_gemini_enterprise_required_fields(self):
        card = build_agent_card(_settings())

        self.assertEqual(card["protocolVersion"], "0.3.0")
        self.assertIn("name", card)
        self.assertIn("url", card)
        self.assertIn("capabilities", card)
        self.assertIn("skills", card)


def _settings() -> RouterSettings:
    return RouterSettings(
        router_name="Transportation Orchestrator Agent",
        router_public_url="https://router.example.com",
        data_agent_url="https://data.example.com",
        map_agent_url="https://map.example.com",
        default_agent="data",
        google_cloud_project="project-id",
        google_cloud_location="global",
        google_genai_use_vertexai=True,
        router_model="gemini-3.5-flash",
        classifier_min_confidence=0.65,
        request_timeout_seconds=120,
        use_id_token=False,
        port=8080,
    )


if __name__ == "__main__":
    unittest.main()
