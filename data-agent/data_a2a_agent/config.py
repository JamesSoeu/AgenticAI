from __future__ import annotations

import os
import re
from dataclasses import dataclass


_TABLE_RE = re.compile(
    r"^(?:(?P<project>[A-Za-z0-9_-]+)\.)?"
    r"(?P<dataset>[A-Za-z_][A-Za-z0-9_]+)\."
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]+)$"
)


@dataclass(frozen=True)
class BigQueryTable:
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


@dataclass(frozen=True)
class Settings:
    google_cloud_project: str
    google_cloud_location: str
    google_genai_use_vertexai: bool
    agent_model: str
    a2a_public_url: str | None
    bigquery_tables: tuple[BigQueryTable, ...]
    bigquery_max_bytes_billed: int
    bigquery_default_limit: int
    bigquery_max_limit: int
    gcs_bucket_name: str | None
    gcs_prefix: str
    gcs_max_text_bytes: int
    gcs_max_pdf_bytes: int
    gcs_max_pdf_pages: int
    gcs_max_pdf_text_chars: int
    port: int

    @property
    def bigquery_table_map(self) -> dict[str, BigQueryTable]:
        return {table.alias: table for table in self.bigquery_tables}


def load_settings() -> Settings:
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    tables = _parse_bigquery_tables(
        raw_tables=os.getenv("BIGQUERY_TABLES", ""),
        raw_aliases=os.getenv("BIGQUERY_TABLE_ALIASES", ""),
        default_project=project,
    )

    return Settings(
        google_cloud_project=project,
        google_cloud_location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip(),
        google_genai_use_vertexai=_parse_bool(os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true")),
        agent_model=os.getenv("AGENT_MODEL", "gemini-2.0-flash").strip(),
        a2a_public_url=os.getenv("A2A_PUBLIC_URL", "").strip() or None,
        bigquery_tables=tuple(tables),
        bigquery_max_bytes_billed=_parse_int("BIGQUERY_MAX_BYTES_BILLED", 1_000_000_000),
        bigquery_default_limit=_parse_int("BIGQUERY_DEFAULT_LIMIT", 100),
        bigquery_max_limit=_parse_int("BIGQUERY_MAX_LIMIT", 1000),
        gcs_bucket_name=os.getenv("GCS_BUCKET_NAME", "").strip() or None,
        gcs_prefix=os.getenv("GCS_PREFIX", "").strip().lstrip("/"),
        gcs_max_text_bytes=_parse_int("GCS_MAX_TEXT_BYTES", 200_000),
        gcs_max_pdf_bytes=_parse_int("GCS_MAX_PDF_BYTES", 25_000_000),
        gcs_max_pdf_pages=_parse_int("GCS_MAX_PDF_PAGES", 20),
        gcs_max_pdf_text_chars=_parse_int("GCS_MAX_PDF_TEXT_CHARS", 60_000),
        port=_parse_int("PORT", 8080),
    )


def _parse_bigquery_tables(
    raw_tables: str, raw_aliases: str, default_project: str
) -> list[BigQueryTable]:
    table_ids = [item.strip() for item in raw_tables.split(",") if item.strip()]
    aliases = [item.strip() for item in raw_aliases.split(",") if item.strip()]
    if aliases and len(aliases) != len(table_ids):
        raise ValueError("BIGQUERY_TABLE_ALIASES must match BIGQUERY_TABLES length.")

    parsed: list[BigQueryTable] = []
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
            BigQueryTable(
                alias=alias,
                project=project,
                dataset=match.group("dataset"),
                table=match.group("table"),
            )
        )
    return parsed


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value
