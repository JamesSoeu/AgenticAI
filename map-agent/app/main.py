# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main entry point for the A2A A2UI sample agent."""

import base64
import html
import json
import os

import uvicorn
from a2a.server import tasks
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from app.agent import BridgeInventoryAgent
from app.agent_executor import BridgeInventoryExecutor
from app.config import AGENT_URL, get_google_maps_api_key

# 1. Create the Agent, AgentCard, RequestHandler, and App.
agent = BridgeInventoryAgent(base_url=AGENT_URL)
agent_card = agent.agent_card

executor = BridgeInventoryExecutor(base_url=AGENT_URL, agent=agent)

request_handler = DefaultRequestHandler(
    agent_executor=executor,
    task_store=tasks.InMemoryTaskStore(),
)

# 2. The Functions Framework will automatically look for this 'app' variable.
app = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=request_handler,
).build()


_ALLOWED_EMBED_MODES = {"place", "directions", "search", "view"}


async def maps_embed_handler(request):
    """Proxy endpoint that redirects to Google Maps Embed API with the real key.

    The LLM constructs URLs like /maps/embed?mode=place&q=... without any
    API key. This endpoint adds the key and redirects to the real embed URL.
    """
    mode = request.query_params.get("mode", "place")
    if mode not in _ALLOWED_EMBED_MODES:
        return JSONResponse({"error": f"Invalid mode: {mode}"}, status_code=400)

    api_key = get_google_maps_api_key()
    if not api_key:
        return JSONResponse({"error": "Maps API key not configured"}, status_code=500)

    # Preserve the original query string (minus the mode param) to avoid
    # any re-encoding issues with URL-encoded values.
    raw_qs = str(request.query_params)
    # Remove mode=... from the query string
    parts = [p for p in raw_qs.split("&") if not p.startswith("mode=")]
    remaining_qs = "&".join(parts)
    url = f"https://www.google.com/maps/embed/v1/{mode}?key={api_key}"
    if remaining_qs:
        url += f"&{remaining_qs}"
    return RedirectResponse(url=url)


async def bridge_map_handler(request):
    """Render an interactive Google map with bridge pins for WebFrameUrl."""
    encoded = request.query_params.get("data", "")
    if not encoded:
        return HTMLResponse("Missing map data", status_code=400)

    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        map_data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except Exception:
        return HTMLResponse("Invalid map data", status_code=400)

    api_key = get_google_maps_api_key()
    if not api_key:
        return HTMLResponse("Maps API key not configured", status_code=500)

    center = map_data.get("center") or {}
    pins = map_data.get("pins") or []
    if not pins or "lat" not in center or "lng" not in center:
        return HTMLResponse("No bridge coordinates available", status_code=400)

    payload = json.dumps(
        {
            "center": center,
            "zoom": map_data.get("zoom", 11),
            "pins": pins[:50],
        },
        separators=(",", ":"),
    ).replace("</", "<\\/")
    escaped_key = html.escape(api_key, quote=True)

    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bridge Map</title>
  <style>
    html, body, #map {{
      height: 100%;
      margin: 0;
      font-family: Arial, sans-serif;
    }}
    .info-title {{
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .info-body {{
      max-width: 280px;
      line-height: 1.35;
    }}
  </style>
</head>
<body>
  <div id="map" aria-label="Bridge locations map"></div>
  <script>
    const mapData = {payload};
    const escapeHtml = (value) => String(value ?? "").replace(
      /[&<>"']/g,
      (char) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[char])
    );
    function initMap() {{
      const map = new google.maps.Map(document.getElementById("map"), {{
        center: mapData.center,
        zoom: mapData.zoom,
        mapTypeControl: true,
        streetViewControl: false,
        fullscreenControl: true
      }});
      const bounds = new google.maps.LatLngBounds();
      const infoWindow = new google.maps.InfoWindow();
      mapData.pins.forEach((pin) => {{
        const position = {{ lat: pin.lat, lng: pin.lng }};
        const marker = new google.maps.Marker({{
          position,
          map,
          title: pin.name
        }});
        marker.addListener("click", () => {{
          infoWindow.setContent(
            `<div class="info-body"><div class="info-title">${{escapeHtml(pin.name)}}</div>` +
            `<div>${{escapeHtml(pin.description)}}</div></div>`
          );
          infoWindow.open({{ anchor: marker, map }});
        }});
        bounds.extend(position);
      }});
      if (mapData.pins.length > 1) {{
        map.fitBounds(bounds, 36);
      }}
    }}
  </script>
  <script async defer src="https://maps.googleapis.com/maps/api/js?key={escaped_key}&callback=initMap"></script>
</body>
</html>"""
    )


async def feedback_handler(request):
    """Dummy feedback handler for tests."""
    return JSONResponse({"status": "ok"})


app.routes.append(Route("/maps/embed", maps_embed_handler))
app.routes.append(Route("/bridge-map", bridge_map_handler))
app.routes.append(Route("/feedback", feedback_handler, methods=["POST"]))

# CORS: restrict to known origins to prevent the /maps/embed proxy from
# being abused as an open API-key relay by third-party sites.
_cors_origins = [
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]
if AGENT_URL and AGENT_URL not in _cors_origins:
    _cors_origins.append(AGENT_URL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
