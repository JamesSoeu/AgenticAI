from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from orchestrator_router.config import RouterSettings


ALLOWED_ROUTES = {"data", "map"}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    confidence: float
    reason: str
    source: str


def classify_route(user_text: str, settings: RouterSettings) -> RouteDecision:
    """Use Gemini to classify a request into one allowed child agent route."""
    if not user_text.strip():
        return RouteDecision(
            route=_valid_default(settings.default_agent),
            confidence=0.0,
            reason="Empty request text; using configured default route.",
            source="fallback",
        )

    try:
        raw_text = _call_gemini_classifier(user_text, settings)
        decision = parse_classifier_response(raw_text)
    except Exception as exc:
        return RouteDecision(
            route=_valid_default(settings.default_agent),
            confidence=0.0,
            reason=f"Classifier failed; using default route. Error: {exc}",
            source="fallback",
        )

    if decision.route not in ALLOWED_ROUTES:
        return RouteDecision(
            route=_valid_default(settings.default_agent),
            confidence=decision.confidence,
            reason=f"Classifier returned invalid route '{decision.route}'.",
            source="fallback",
        )
    if decision.confidence < settings.classifier_min_confidence:
        return RouteDecision(
            route=_valid_default(settings.default_agent),
            confidence=decision.confidence,
            reason=(
                "Classifier confidence below threshold; using configured "
                f"default route. Classifier reason: {decision.reason}"
            ),
            source="fallback",
        )
    return decision


def parse_classifier_response(raw_text: str) -> RouteDecision:
    """Parse the strict JSON response returned by the routing LLM."""
    payload = json.loads(_extract_json_object(raw_text))
    route = str(payload.get("route", "")).strip().lower()
    confidence = float(payload.get("confidence", 0.0))
    reason = str(payload.get("reason", "")).strip()
    if not reason:
        reason = "No classifier reason provided."
    return RouteDecision(
        route=route,
        confidence=max(0.0, min(confidence, 1.0)),
        reason=reason,
        source="llm",
    )


def _call_gemini_classifier(user_text: str, settings: RouterSettings) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=settings.google_genai_use_vertexai,
        project=settings.google_cloud_project or None,
        location=settings.google_cloud_location,
    )
    response = client.models.generate_content(
        model=settings.router_model,
        contents=_classifier_prompt(user_text),
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("Gemini classifier returned an empty response.")
    return text


def _classifier_prompt(user_text: str) -> str:
    return f"""You are the routing classifier for a Gemini Enterprise A2A multi-agent system.

Choose exactly one route from this allowlist:

1. data
   Use for BigQuery analytics, Cloud Storage files, PDF/manual questions,
   table counts, schemas, columns, previews, SQL-style questions, crash
   analysis, road analysis, traffic analysis, EILIS questions, summaries,
   comparisons, and document search.

2. map
   Use for bridge location lookup, Google Maps display, A2UI map display,
   coordinates, where-is questions, county/crossing map views, structure/SFN
   visual lookup, and requests where the user wants to see bridges on a map.

Return only valid JSON with this exact shape:
{{
  "route": "data" | "map",
  "confidence": 0.0,
  "reason": "short reason"
}}

Do not include markdown. Do not include extra keys. Do not invent another route.

User request:
{user_text}
"""


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in classifier response: {raw_text!r}")
    return text[start : end + 1]


def _valid_default(default_agent: str) -> str:
    return default_agent if default_agent in ALLOWED_ROUTES else "data"
