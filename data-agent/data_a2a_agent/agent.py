from __future__ import annotations

import logging

from starlette.applications import Starlette
from starlette.responses import JSONResponse

from data_a2a_agent.config import load_settings
from data_a2a_agent.tools import (
    describe_bigquery_tables,
    list_configured_sources,
    list_gcs_objects,
    preview_bigquery_table,
    read_gcs_pdf_object,
    read_gcs_text_object,
    run_bigquery_select,
    search_gcs_pdf_object,
)


settings = load_settings()


def _build_instruction() -> str:
    table_lines = "\n".join(
        f"- {table.alias}: {table.full_id}" for table in settings.bigquery_tables
    ) or "- No BigQuery tables configured yet."
    bucket = settings.gcs_bucket_name or "No Cloud Storage bucket configured yet."
    prefix = settings.gcs_prefix or "(bucket root)"
    return f"""
You are a transportation infrastructure data agent exposed over the A2A protocol
for Gemini Enterprise.

Use only the configured BigQuery tables and Cloud Storage bucket. Do not invent
table names, bucket names, columns, counts, locations, crash totals, bridge ratings,
traffic measurements, or source content. Inspect schemas before writing analytical
SQL unless the user provides exact columns. Prefer concise answers with the query
or object source used.

Primary data domains:
- bridge: bridge inventory, asset attributes, condition, structure, inspection, or location data.
- crash: crash, collision, safety, severity, location, date, and related roadway safety data.
- eilis: EILIS reference or event data. Inspect the schema before assuming columns.
- road: roadway inventory, route, segment, jurisdiction, classification, or location data.
- traffic: traffic counts, volume, speed, station, route, or time-based traffic data.

Configured BigQuery tables:
{table_lines}

Configured Cloud Storage source:
- bucket: {bucket}
- prefix: {prefix}

When querying BigQuery:
- Use describe_bigquery_tables first when the needed schema is unclear.
- Use run_bigquery_select only for SELECT or WITH queries.
- Keep result sets small and aggregate when possible.
- Join tables only when there is a clear key in the schema, such as route, segment,
  asset id, county, date, station, or another documented field.
- Explain if a request needs a table, column, or file that is not configured.

When reading Cloud Storage:
- Use list_gcs_objects to discover candidate files.
- Use read_gcs_text_object for text files only.
- Use search_gcs_pdf_object to answer questions from PDF manuals or guides.
- Use read_gcs_pdf_object when the user asks for selected pages or when search
  results need more surrounding context.
- Cite PDF object names and page numbers when answering from PDF content.

Good tasks you can help with:
- Summarize bridge inventory counts by county, route, structure type, or condition field.
- Find crash patterns by date, severity, road segment, route, or location.
- Compare roadway inventory with crash or traffic data when schemas provide join keys.
- Identify high traffic corridors or traffic count trends from the traffic table.
- Locate supporting files in Cloud Storage and summarize relevant text or PDF content.
""".strip()


try:
    from a2a.server.apps import A2AStarletteApplication
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore
    from google.adk import Agent
    from google.adk.a2a.converters.part_converter import convert_a2a_part_to_genai_part
    from google.adk.a2a.converters.request_converter import AgentRunRequest
    from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
    from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutorConfig
    from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
    from google.adk.auth.credential_service.in_memory_credential_service import (
        InMemoryCredentialService,
    )
    from google.adk.cli.utils.logs import setup_adk_logger
    from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
    from google.adk.runners import RunConfig
    from google.adk.runners import Runner
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google.genai import types as genai_types
except ImportError as exc:  # pragma: no cover - exercised only without dependencies.
    raise RuntimeError(
        "google-adk[a2a] is required. Install dependencies with `pip install -r requirements.txt`."
    ) from exc

logger = logging.getLogger(__name__)


root_agent = Agent(
    name="transportation_data_a2a_agent",
    model=settings.agent_model,
    description=(
        "A2A ADK agent that answers transportation infrastructure questions using "
        "configured BigQuery bridge, crash, EILIS, road, and traffic tables plus "
        "Google Cloud Storage text sources."
    ),
    instruction=_build_instruction(),
    tools=[
        list_configured_sources,
        describe_bigquery_tables,
        preview_bigquery_table,
        run_bigquery_select,
        list_gcs_objects,
        read_gcs_text_object,
        read_gcs_pdf_object,
        search_gcs_pdf_object,
    ],
)


def _get_user_id(request) -> str:
    if (
        request.call_context
        and request.call_context.user
        and request.call_context.user.user_name
    ):
        return request.call_context.user.user_name
    return f"A2A_USER_{request.context_id}"


def _convert_request_without_part_metadata(
    request,
    part_converter=convert_a2a_part_to_genai_part,
) -> AgentRunRequest:
    """Convert A2A requests without metadata unsupported by Gemini Enterprise.

    google-adk 1.18.x copies A2A request metadata into RunConfig.custom_metadata.
    In Gemini Enterprise Agent Platform mode that can surface as `part_metadata`,
    which the platform rejects. The user text and files are still converted; only
    request/part metadata is omitted.
    """
    if not request.message:
        raise ValueError("Request message cannot be None")

    genai_parts = []
    for a2a_part in request.message.parts:
        genai_part = part_converter(a2a_part)
        if genai_part is None:
            continue
        if hasattr(genai_part, "part_metadata"):
            try:
                genai_part.part_metadata = None
            except Exception:
                logger.debug("Could not clear GenAI part_metadata", exc_info=True)
        genai_parts.append(genai_part)

    return AgentRunRequest(
        user_id=_get_user_id(request),
        session_id=request.context_id,
        new_message=genai_types.Content(role="user", parts=genai_parts),
        run_config=RunConfig(custom_metadata=None),
    )


def _build_a2a_app() -> Starlette:
    setup_adk_logger(logging.INFO)

    async def create_runner() -> Runner:
        return Runner(
            app_name=root_agent.name or "adk_agent",
            agent=root_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            credential_service=InMemoryCredentialService(),
        )

    task_store = InMemoryTaskStore()
    agent_executor = A2aAgentExecutor(
        runner=create_runner,
        config=A2aAgentExecutorConfig(
            request_converter=_convert_request_without_part_metadata,
        ),
    )
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
    )

    app = Starlette()
    a2a_app = A2AStarletteApplication(
        agent_card=_agent_card(),
        http_handler=request_handler,
    )
    a2a_app.add_routes_to_app(app)
    return app


def _agent_card():
    public_url = settings.a2a_public_url or f"http://localhost:{settings.port}"
    try:
        from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

        skill = AgentSkill(
            id="transportation_infrastructure_question_answering",
            name="Transportation Infrastructure Data Question Answering",
            description=(
                "Answers transportation infrastructure questions with an allowlist "
                "of BigQuery bridge, crash, EILIS, road, and traffic tables plus a "
                "configured Google Cloud Storage bucket."
            ),
            input_modes=["text/plain"],
            output_modes=["text/plain"],
            tags=[
                "bigquery",
                "cloud-storage",
                "gemini-enterprise",
                "a2a",
                "bridge-inventory",
                "crash-analysis",
                "roadway-data",
                "traffic-data",
            ],
            examples=[
                "How many bridge records are available by county or route?",
                "Show crash counts by severity and month for the latest year in the crash table.",
                "Find road segments with high crash counts and available traffic volume data.",
                "Summarize traffic count trends by route or station.",
                "Search the bridge inspection PDF manuals for inspection responsibility.",
                "List source files in the mio-poc bucket and summarize a relevant PDF or text file.",
            ],
        )

        base_card = {
            "name": "Transportation Data A2A Agent",
            "description": (
                "ADK agent for Gemini Enterprise that queries configured BigQuery "
                "bridge, crash, EILIS, road, and traffic tables and reads text data "
                "from Google Cloud Storage."
            ),
            "version": "0.1.0",
            "default_input_modes": ["text/plain"],
            "default_output_modes": ["text/plain"],
            "capabilities": AgentCapabilities(streaming=True, extended_agent_card=False),
            "skills": [skill],
        }

        # A2A SDK releases have used both names for the protocol field.
        # Cloud Run logs from google-adk 1.18.x show `transport` is required,
        # while the public tutorial still shows `protocol_binding`.
        for interface in (
            {"transport": "JSONRPC", "url": public_url},
            {"protocol_binding": "JSONRPC", "url": public_url},
        ):
            for include_legacy_url in (False, True):
                try:
                    card = dict(base_card)
                    card["supported_interfaces"] = [AgentInterface(**interface)]
                    if include_legacy_url:
                        card["url"] = public_url
                    return AgentCard(**card)
                except Exception:
                    continue

        raise RuntimeError("Could not build an A2A AgentCard with this A2A SDK version.")
    except (ImportError, TypeError, RuntimeError):
        from a2a.types import AgentCard

        return AgentCard(
            name="Transportation Data A2A Agent",
            url=public_url,
            description=(
                "ADK agent for Gemini Enterprise that queries configured BigQuery "
                "bridge, crash, EILIS, road, and traffic tables and reads text data "
                "from Google Cloud Storage."
            ),
            version="0.1.0",
            capabilities={},
            skills=[],
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            supports_authenticated_extended_card=False,
        )


a2a_app = _build_a2a_app()


async def healthz(_request):
    configured = load_settings()
    return JSONResponse(
        {
            "status": "ok",
            "agent": root_agent.name,
            "bigquery_table_count": len(configured.bigquery_tables),
            "gcs_bucket_configured": bool(configured.gcs_bucket_name),
        }
    )


a2a_app.add_route("/healthz", healthz, methods=["GET"])
