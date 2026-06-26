from __future__ import annotations

from io import BytesIO
import re
from typing import Any

from data_a2a_agent.config import BigQueryTable, load_settings
from data_a2a_agent.session_keys import A2UI_CATALOG_KEY
from data_a2a_agent.table_ui import build_bigquery_table_a2ui

try:  # pragma: no cover - google-adk is available in deployed agent runtime.
    from google.adk.tools.tool_context import ToolContext
except Exception:  # pragma: no cover - keeps local unit tests dependency-light.
    ToolContext = Any


_BLOCKED_SQL = re.compile(
    r"\b(ALTER|CALL|CREATE|DELETE|DROP|EXPORT|GRANT|INSERT|MERGE|REPLACE|REVOKE|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)
_FROM_OR_JOIN = re.compile(
    r"\b(?:FROM|JOIN)\s+`?([A-Za-z0-9_-]+\.[A-Za-z_][A-Za-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]+)`?",
    re.IGNORECASE,
)


def list_configured_sources() -> dict[str, Any]:
    """List BigQuery tables and Cloud Storage source configured for this agent."""
    settings = load_settings()
    return {
        "bigquery_tables": [
            {"alias": table.alias, "table": table.full_id} for table in settings.bigquery_tables
        ],
        "gcs": {"bucket": settings.gcs_bucket_name, "prefix": settings.gcs_prefix},
    }


def describe_bigquery_tables(table_aliases: list[str] | None = None) -> dict[str, Any]:
    """Return schema metadata for configured BigQuery tables."""
    settings = load_settings()
    selected_tables = _select_tables(table_aliases)
    client = _bigquery_client(project=settings.google_cloud_project)

    results: list[dict[str, Any]] = []
    for table in selected_tables:
        bq_table = client.get_table(table.full_id)
        results.append(
            {
                "alias": table.alias,
                "table": table.full_id,
                "description": bq_table.description,
                "num_rows": bq_table.num_rows,
                "schema": [
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "mode": field.mode,
                        "description": field.description,
                    }
                    for field in bq_table.schema
                ],
            }
        )
    return {"tables": results}


def preview_bigquery_table(table_alias: str, limit: int | None = None) -> dict[str, Any]:
    """Preview rows from a configured BigQuery table by alias."""
    settings = load_settings()
    table = _get_table(table_alias)
    row_limit = _bounded_limit(limit, settings.bigquery_default_limit, settings.bigquery_max_limit)
    sql = f"SELECT * FROM {table.sql_ref} LIMIT {row_limit}"
    return run_bigquery_select(sql)


def run_bigquery_select(
    sql: str,
    limit: int | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run a read-only SELECT query against the configured BigQuery tables."""
    settings = load_settings()
    clean_sql = _validate_select_sql(sql, settings.bigquery_tables)
    row_limit = _bounded_limit(limit, settings.bigquery_default_limit, settings.bigquery_max_limit)
    clean_sql = _ensure_limit(clean_sql, row_limit)

    bigquery = _import_bigquery()
    client = bigquery.Client(project=settings.google_cloud_project or None)
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=settings.bigquery_max_bytes_billed,
        labels={"component": "a2a-adk-agent"},
    )
    rows = client.query(clean_sql, job_config=job_config).result()
    data = [dict(row.items()) for row in rows]
    result = {
        "sql": clean_sql,
        "row_count": len(data),
        "rows": data,
        "markdown_table": rows_to_markdown_table(data),
    }
    if tool_context is not None:
        catalog = tool_context.state.get(A2UI_CATALOG_KEY)
        result["validated_a2ui_json"] = build_bigquery_table_a2ui(
            rows=data,
            sql=clean_sql,
            version=getattr(catalog, "version", None),
            catalog_id=getattr(catalog, "catalog_id", None),
        )
        tool_context.actions.skip_summarization = True
    return result


def rows_to_markdown_table(rows: list[dict[str, Any]], max_rows: int = 50) -> str:
    """Format query rows as a GitHub-flavored Markdown table."""
    if not rows:
        return "_No rows returned._"

    columns = list(rows[0].keys())
    for row in rows[1:]:
        for column in row.keys():
            if column not in columns:
                columns.append(column)

    visible_rows = rows[: max(max_rows, 1)]
    header = "| " + " | ".join(_markdown_cell(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| "
        + " | ".join(_markdown_cell(row.get(column)) for column in columns)
        + " |"
        for row in visible_rows
    ]
    if len(rows) > len(visible_rows):
        body.append(
            "| "
            + " | ".join(
                _markdown_cell(
                    f"Showing {len(visible_rows)} of {len(rows)} rows"
                    if index == 0
                    else ""
                )
                for index, _ in enumerate(columns)
            )
            + " |"
        )
    return "\n".join([header, separator, *body])


def list_gcs_objects(prefix: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List Cloud Storage objects under the configured bucket and prefix."""
    settings = load_settings()
    bucket_name = _require_bucket(settings.gcs_bucket_name)
    object_prefix = _combine_prefix(settings.gcs_prefix, prefix)
    storage = _import_storage()
    client = storage.Client(project=settings.google_cloud_project or None)
    blobs = client.list_blobs(bucket_name, prefix=object_prefix, max_results=min(max(limit, 1), 500))
    return {
        "bucket": bucket_name,
        "prefix": object_prefix,
        "objects": [
            {
                "name": blob.name,
                "size": blob.size,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "content_type": blob.content_type,
            }
            for blob in blobs
        ],
    }


def read_gcs_text_object(blob_name: str, max_bytes: int | None = None) -> dict[str, Any]:
    """Read a UTF-8 text object from the configured Cloud Storage bucket."""
    settings = load_settings()
    bucket_name = _require_bucket(settings.gcs_bucket_name)
    _assert_blob_allowed(settings.gcs_prefix, blob_name)
    byte_limit = min(max_bytes or settings.gcs_max_text_bytes, settings.gcs_max_text_bytes)

    storage = _import_storage()
    client = storage.Client(project=settings.google_cloud_project or None)
    blob = client.bucket(bucket_name).blob(blob_name)
    raw = blob.download_as_bytes(start=0, end=byte_limit - 1)
    text = raw.decode("utf-8", errors="replace")
    return {
        "bucket": bucket_name,
        "name": blob_name,
        "bytes_returned": len(raw),
        "truncated": len(raw) == byte_limit,
        "text": text,
    }


def read_gcs_pdf_object(
    blob_name: str,
    start_page: int = 1,
    page_count: int | None = None,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Extract text from selected pages of a PDF in the configured GCS bucket."""
    settings = load_settings()
    bucket_name = _require_bucket(settings.gcs_bucket_name)
    _assert_blob_allowed(settings.gcs_prefix, blob_name)
    _assert_pdf_name(blob_name)

    reader = _download_pdf_reader(bucket_name, blob_name)
    total_pages = len(reader.pages)
    first_page = max(1, int(start_page))
    max_pages = min(page_count or settings.gcs_max_pdf_pages, settings.gcs_max_pdf_pages)
    last_page = min(total_pages, first_page + max_pages - 1)
    char_limit = min(max_chars or settings.gcs_max_pdf_text_chars, settings.gcs_max_pdf_text_chars)

    pages: list[dict[str, Any]] = []
    chars_used = 0
    for page_number in range(first_page, last_page + 1):
        text = _extract_pdf_page_text(reader, page_number)
        remaining = char_limit - chars_used
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining]
        chars_used += len(text)
        pages.append({"page": page_number, "text": text})

    return {
        "bucket": bucket_name,
        "name": blob_name,
        "total_pages": total_pages,
        "start_page": first_page,
        "pages_returned": len(pages),
        "truncated": chars_used >= char_limit or last_page < total_pages,
        "pages": pages,
    }


def search_gcs_pdf_object(
    blob_name: str,
    query: str,
    max_matches: int = 8,
    context_chars: int = 700,
) -> dict[str, Any]:
    """Search extracted PDF text and return page snippets with surrounding context."""
    settings = load_settings()
    bucket_name = _require_bucket(settings.gcs_bucket_name)
    _assert_blob_allowed(settings.gcs_prefix, blob_name)
    _assert_pdf_name(blob_name)

    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9]+", query) if len(term) > 2]
    if not terms:
        raise ValueError("Search query must contain at least one meaningful term.")

    reader = _download_pdf_reader(bucket_name, blob_name)
    total_pages = len(reader.pages)
    page_limit = min(total_pages, settings.gcs_max_pdf_pages)
    match_limit = min(max(1, int(max_matches)), 20)
    context = min(max(100, int(context_chars)), 2_000)

    matches: list[dict[str, Any]] = []
    for page_number in range(1, page_limit + 1):
        text = _extract_pdf_page_text(reader, page_number)
        lower_text = text.lower()
        positions = [
            lower_text.find(term)
            for term in terms
            if lower_text.find(term) >= 0
        ]
        if not positions:
            continue
        index = min(positions)
        start = max(0, index - context)
        end = min(len(text), index + context)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        matches.append({"page": page_number, "snippet": snippet})
        if len(matches) >= match_limit:
            break

    return {
        "bucket": bucket_name,
        "name": blob_name,
        "query": query,
        "total_pages": total_pages,
        "pages_searched": page_limit,
        "matches": matches,
        "truncated": page_limit < total_pages,
    }


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _select_tables(table_aliases: list[str] | None) -> list[BigQueryTable]:
    settings = load_settings()
    if not table_aliases:
        return list(settings.bigquery_tables)
    return [_get_table(alias) for alias in table_aliases]


def _get_table(alias: str) -> BigQueryTable:
    settings = load_settings()
    table = settings.bigquery_table_map.get(alias)
    if not table:
        known = ", ".join(sorted(settings.bigquery_table_map)) or "(none configured)"
        raise ValueError(f"Unknown table alias '{alias}'. Known aliases: {known}.")
    return table


def _validate_select_sql(sql: str, allowed_tables: tuple[BigQueryTable, ...]) -> str:
    clean_sql = sql.strip().rstrip(";").strip()
    if not clean_sql:
        raise ValueError("SQL query is empty.")
    if not re.match(r"^(WITH|SELECT)\b", clean_sql, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in clean_sql:
        raise ValueError("Multiple SQL statements are not allowed.")
    if _BLOCKED_SQL.search(clean_sql):
        raise ValueError("Mutation, DDL, export, and permission statements are not allowed.")

    referenced_tables = set(_FROM_OR_JOIN.findall(clean_sql))
    allowed_ids = {table.full_id for table in allowed_tables}
    if not referenced_tables:
        raise ValueError("Query must reference at least one configured table.")
    disallowed = referenced_tables - allowed_ids
    if disallowed:
        raise ValueError(
            "Query references non-configured tables: " + ", ".join(sorted(disallowed))
        )
    return clean_sql


def _ensure_limit(sql: str, limit: int) -> str:
    if re.search(r"\bLIMIT\s+\d+\s*$", sql, re.IGNORECASE):
        return sql
    return f"SELECT * FROM ({sql}) LIMIT {limit}"


def _bounded_limit(limit: int | None, default: int, maximum: int) -> int:
    value = default if limit is None else int(limit)
    return max(1, min(value, maximum))


def _combine_prefix(base_prefix: str, requested_prefix: str | None) -> str:
    requested = (requested_prefix or "").strip().lstrip("/")
    base = base_prefix.strip().strip("/")
    if not base:
        return requested
    if not requested:
        return f"{base}/"
    combined = f"{base}/{requested}"
    _assert_blob_allowed(base, combined)
    return combined


def _assert_blob_allowed(base_prefix: str, blob_name: str) -> None:
    normalized = blob_name.strip().lstrip("/")
    if ".." in normalized.split("/"):
        raise ValueError("Object paths cannot contain '..'.")
    base = base_prefix.strip().strip("/")
    if base and not (normalized == base or normalized.startswith(f"{base}/")):
        raise ValueError(f"Object must be under configured prefix '{base}/'.")


def _require_bucket(bucket_name: str | None) -> str:
    if not bucket_name:
        raise ValueError("GCS_BUCKET_NAME is not configured.")
    return bucket_name


def _assert_pdf_name(blob_name: str) -> None:
    if not blob_name.lower().endswith(".pdf"):
        raise ValueError("Object must be a PDF file ending in .pdf.")


def _download_pdf_reader(bucket_name: str, blob_name: str):
    settings = load_settings()
    storage = _import_storage()
    client = storage.Client(project=settings.google_cloud_project or None)
    blob = client.bucket(bucket_name).blob(blob_name)
    blob.reload()
    if blob.size and blob.size > settings.gcs_max_pdf_bytes:
        raise ValueError(
            f"PDF is too large: {blob.size} bytes exceeds GCS_MAX_PDF_BYTES."
        )
    raw = blob.download_as_bytes()
    if len(raw) > settings.gcs_max_pdf_bytes:
        raise ValueError(
            f"PDF is too large: {len(raw)} bytes exceeds GCS_MAX_PDF_BYTES."
        )

    from pypdf import PdfReader

    return PdfReader(BytesIO(raw))


def _extract_pdf_page_text(reader, page_number: int) -> str:
    page = reader.pages[page_number - 1]
    text = page.extract_text() or ""
    return text.strip()


def _bigquery_client(project: str):
    bigquery = _import_bigquery()
    return bigquery.Client(project=project or None)


def _import_bigquery():
    from google.cloud import bigquery

    return bigquery


def _import_storage():
    from google.cloud import storage

    return storage
