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

"""Centralized configuration for the bridge inventory agent.

All environment-driven settings live here. For local development, values
are loaded from a `.env` file via ``dotenv``. For deployment, they are
injected as environment variables (see Makefile ``deploy`` target and
Cloud Build configs).
"""

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google Cloud
# ---------------------------------------------------------------------------
GOOGLE_CLOUD_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
# Vertex AI location for Gemini API calls. The genai SDK derives the
# endpoint from this value (`global` -> aiplatform.googleapis.com,
# `<region>` -> <region>-aiplatform.googleapis.com).
# gemini-3-flash-preview and gemini-3.1-flash-lite-preview are only
# served from the global endpoint; do not set this to a regional value
# when using those models.
GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
A2UI_EXTENSION_URI_V0_8 = "https://a2ui.org/a2a-extension/a2ui/v0.8"
A2UI_EXTENSION_URI = "https://a2ui.org/a2a-extension/a2ui/v0.9"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
DEFAULT_MODEL: str = os.getenv("MODEL", "gemini-3.5-flash")
GOOGLE_GENAI_USE_VERTEXAI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
AGENT_URL: str = os.getenv("AGENT_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Map BigQuery tables
# ---------------------------------------------------------------------------
_TABLE_RE = re.compile(
    r"^(?:(?P<project>[A-Za-z0-9_-]+)\.)?"
    r"(?P<dataset>[A-Za-z_][A-Za-z0-9_]+)\."
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]+)$"
)


@dataclass(frozen=True)
class MapBigQueryTable:
    alias: str
    project: str
    dataset: str
    table: str

    @property
    def full_id(self) -> str:
        return f"{self.project}.{self.dataset}.{self.table}"

    @property
    def sql_ref(self) -> str:
        return f"`{self.full_id}`"


BRIDGE_BIGQUERY_TABLE: str = os.getenv(
    "BRIDGE_BIGQUERY_TABLE",
    "your-project-id.transportation.bridge_data",
)
BRIDGE_BIGQUERY_TABLES: tuple[str, ...] = ()
MAP_BIGQUERY_TABLES: tuple[MapBigQueryTable, ...] = ()


def _parse_table_list(raw: str) -> tuple[str, ...]:
    """Parse comma-separated BigQuery table IDs.

    Accepts accidental pasted values such as
    ``BIGQUERY_TABLES=project.dataset.table,...`` so deployment config errors
    are easier to recover from.
    """
    value = raw.strip().strip('"').strip("'")
    if "=" in value and value.split("=", maxsplit=1)[0].strip().endswith("TABLES"):
        value = value.split("=", maxsplit=1)[1]
    return tuple(table.strip() for table in value.split(",") if table.strip())


def _parse_map_tables(
    raw_tables: str,
    raw_aliases: str,
    default_project: str | None,
) -> tuple[MapBigQueryTable, ...]:
    table_ids = _parse_table_list(raw_tables)
    aliases = [item.strip() for item in raw_aliases.split(",") if item.strip()]
    if aliases and len(aliases) != len(table_ids):
        raise ValueError("MAP_BIGQUERY_TABLE_ALIASES must match MAP_BIGQUERY_TABLES length.")

    parsed: list[MapBigQueryTable] = []
    seen_aliases: set[str] = set()
    for index, table_id in enumerate(table_ids):
        match = _TABLE_RE.match(table_id)
        if not match:
            raise ValueError(
                f"Invalid BigQuery table id '{table_id}'. Use project.dataset.table or dataset.table."
            )
        project = match.group("project") or default_project
        if not project:
            raise ValueError(
                f"BigQuery table '{table_id}' needs a project or GOOGLE_CLOUD_PROJECT."
            )

        alias = aliases[index] if aliases else match.group("table")
        if not re.match(r"^[A-Za-z][A-Za-z0-9_-]{0,62}$", alias):
            raise ValueError(f"Invalid BigQuery table alias '{alias}'.")
        if alias in seen_aliases:
            raise ValueError(f"Duplicate BigQuery table alias '{alias}'.")
        seen_aliases.add(alias)

        parsed.append(
            MapBigQueryTable(
                alias=alias,
                project=project,
                dataset=match.group("dataset"),
                table=match.group("table"),
            )
        )
    return tuple(parsed)


BRIDGE_BIGQUERY_TABLES = _parse_table_list(
    os.getenv("MAP_BIGQUERY_TABLES")
    or os.getenv("BRIDGE_BIGQUERY_TABLES")
    or os.getenv("BIGQUERY_TABLES")
    or BRIDGE_BIGQUERY_TABLE
)
BRIDGE_BIGQUERY_TABLE = BRIDGE_BIGQUERY_TABLES[0] if BRIDGE_BIGQUERY_TABLES else BRIDGE_BIGQUERY_TABLE
MAP_BIGQUERY_TABLES = _parse_map_tables(
    raw_tables=(
        os.getenv("MAP_BIGQUERY_TABLES")
        or os.getenv("BRIDGE_BIGQUERY_TABLES")
        or os.getenv("BIGQUERY_TABLES")
        or BRIDGE_BIGQUERY_TABLE
    ),
    raw_aliases=(
        os.getenv("MAP_BIGQUERY_TABLE_ALIASES")
        or os.getenv("BRIDGE_BIGQUERY_TABLE_ALIASES")
        or os.getenv("BIGQUERY_TABLE_ALIASES")
        or ""
    ),
    default_project=GOOGLE_CLOUD_PROJECT,
)
BIGQUERY_JOB_PROJECT: str = os.getenv(
    "BIGQUERY_JOB_PROJECT",
    GOOGLE_CLOUD_PROJECT or BRIDGE_BIGQUERY_TABLE.split(".", maxsplit=1)[0],
)
BIGQUERY_LOCATION: str = os.getenv("BIGQUERY_LOCATION", "")
MAP_BIGQUERY_MAX_BYTES_BILLED: int = int(os.getenv("MAP_BIGQUERY_MAX_BYTES_BILLED", "1000000000"))
MAP_DEFAULT_LIMIT: int = int(os.getenv("MAP_DEFAULT_LIMIT", "10"))
MAP_MAX_LIMIT: int = int(os.getenv("MAP_MAX_LIMIT", "50"))

# ---------------------------------------------------------------------------
# Google Maps
# ---------------------------------------------------------------------------
_MAPS_SECRET_NAME: str = os.getenv("GOOGLE_MAPS_SECRET_NAME", "google_map_api_key")
_MAPS_SECRET_LOCATION: str = os.getenv("GOOGLE_MAPS_SECRET_LOCATION", "")
_MAPS_SECRET_RESOURCE: str = os.getenv("GOOGLE_MAPS_SECRET_RESOURCE", "")


_cached_maps_api_key: str | None = None


def get_google_maps_api_key() -> str | None:
    """Fetch Google Maps API key from env var or Secret Manager."""
    global _cached_maps_api_key
    if _cached_maps_api_key is not None:
        return _cached_maps_api_key

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if api_key:
        _cached_maps_api_key = api_key
        return api_key

    if not GOOGLE_CLOUD_PROJECT:
        logger.warning("GOOGLE_CLOUD_PROJECT not set; cannot fetch Maps API key")
        return None

    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        secret_names: list[str] = []
        if _MAPS_SECRET_RESOURCE:
            secret_names.append(_MAPS_SECRET_RESOURCE)
        if _MAPS_SECRET_LOCATION:
            secret_names.append(
                f"projects/{GOOGLE_CLOUD_PROJECT}"
                f"/locations/{_MAPS_SECRET_LOCATION}"
                f"/secrets/{_MAPS_SECRET_NAME}/versions/latest"
            )
        secret_names.append(
            f"projects/{GOOGLE_CLOUD_PROJECT}"
            f"/secrets/{_MAPS_SECRET_NAME}/versions/latest"
        )

        errors: list[tuple[str, Exception]] = []
        for name in secret_names:
            try:
                response = client.access_secret_version(request={"name": name})
                _cached_maps_api_key = response.payload.data.decode("UTF-8")
                return _cached_maps_api_key
            except Exception as exc:
                errors.append((name, exc))

        for name, exc in errors:
            logger.warning(
                "Failed to fetch Maps API key from %s: %s",
                name,
                exc,
            )
    except Exception:
        logger.warning(
            "Failed to fetch Maps API key from Secret Manager", exc_info=True
        )
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_vertex_model_name(model: str | None = None) -> str:
    """Return a fully-qualified Vertex AI model resource name.

    Falls back to a bare model ID when ``GOOGLE_CLOUD_PROJECT`` is unset
    (e.g. local dev without Vertex).
    """
    model = model or DEFAULT_MODEL
    if GOOGLE_CLOUD_PROJECT:
        return (
            f"projects/{GOOGLE_CLOUD_PROJECT}"
            f"/locations/{GOOGLE_CLOUD_LOCATION}"
            f"/publishers/google/models/{model}"
        )
    return model


def extract_json_from_llm_response(text: str) -> str:
    """Strip optional markdown code fences from an LLM response."""
    text = text.strip()
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        return text[start:end].strip()
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        return text[start:end].strip()
    return text


def build_maps_embed_url(
    *,
    query: str | None = None,
    center: str | None = None,
    zoom: int | None = None,
    origin: str | None = None,
    destination: str | None = None,
) -> str | None:
    """Build a Google Maps Embed API URL.

    Returns ``None`` when the API key is unavailable.
    """
    api_key = get_google_maps_api_key()
    if not api_key:
        logger.warning("Google Maps API key not available; cannot build embed URL")
        return None

    base = "https://www.google.com/maps/embed/v1"
    if origin and destination:
        return (
            f"{base}/directions?key={api_key}"
            f"&origin={quote(origin)}&destination={quote(destination)}"
        )
    if center:
        url = f"{base}/view?key={api_key}&center={quote(center)}"
        if zoom is not None:
            url += f"&zoom={max(1, min(int(zoom), 21))}"
        return url
    if query:
        return f"{base}/place?key={api_key}&q={quote(query)}"
    return None
