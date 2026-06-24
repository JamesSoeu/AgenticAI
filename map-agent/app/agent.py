"""Bridge inventory agent using BigQuery and A2UI."""

import os
from typing import ClassVar

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2ui.a2a.extension import get_a2ui_agent_extension
from a2ui.basic_catalog.provider import BasicCatalog, BundledCatalogProvider
from a2ui.schema.catalog import CatalogConfig
from a2ui.schema.catalog_provider import (
    A2uiCatalogProvider,
    FileSystemCatalogProvider,
)
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import (
    CATALOG_COMPONENTS_KEY,
    CATALOG_ID_KEY,
    VERSION_0_8,
    VERSION_0_9,
)
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.bridge_tools import search_bridges
from app.config import DEFAULT_MODEL
from app.session_keys import A2UI_CATALOG_KEY

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_DEFINITION_V0_8 = os.path.join(
    _APP_DIR, "catalog_schemas", "0.8", "bridge_map_catalog.json"
)
CATALOG_DEFINITION_V0_9 = os.path.join(
    _APP_DIR, "catalog_schemas", "0.9", "bridge_map_catalog.json"
)

ROLE_DESCRIPTION = """
You are the Bridge Inventory Agent for Gemini Enterprise.
Help users search the configured BigQuery bridge/map tables and display the
matching bridge details and map inside the chat window.

For every bridge or map request, call `search_bridges` exactly once. Use only
values returned by that tool; never invent bridge details. The tool
automatically renders matching bridge results in the chat window. Do not write A2UI JSON and do not call any additional rendering function.
"""

WORKFLOW_DESCRIPTION = """
1. Translate the user's request into `search_bridges` filters. Use `query` for
   general search text and the specific parameters for county code, route code,
   structure ID, location, or crossed feature.
2. Call `search_bridges` exactly once. Never write SQL yourself.
3. If the tool returns no bridges, clearly say no matching bridges were found
   and do not create an empty UI.
4. The search tool automatically renders all returned key columns, source table,
   and one map containing every bridge with valid coordinates as pins. Do not
   ask Google Maps to create a directions route between bridge locations.
5. Never output raw JSON, Python code, A2UI markup, or a rendering function call.
"""

class _MergedBasicCatalogProvider(A2uiCatalogProvider):
    """Merge the v0.9 basic catalog with the bridge map components."""

    def __init__(self, custom_catalog_path: str):
        self._basic = BundledCatalogProvider(VERSION_0_9)
        self._custom = FileSystemCatalogProvider(custom_catalog_path)

    def load(self) -> dict:
        merged = self._basic.load()
        custom = self._custom.load()
        merged[CATALOG_ID_KEY] = "https://a2ui.org/specification/v0_9/basic_catalog.json"

        custom_components = custom.get(CATALOG_COMPONENTS_KEY, {})
        merged.setdefault(CATALOG_COMPONENTS_KEY, {}).update(custom_components)

        any_component = merged.setdefault("$defs", {}).setdefault(
            "anyComponent",
            {"oneOf": [], "discriminator": {"propertyName": "component"}},
        )
        refs = {
            item.get("$ref")
            for item in any_component.setdefault("oneOf", [])
            if isinstance(item, dict)
        }
        for name in custom_components:
            ref = f"#/{CATALOG_COMPONENTS_KEY}/{name}"
            if ref not in refs:
                any_component["oneOf"].append({"$ref": ref})

        return merged


class BridgeInventoryAgent:
    """A2A agent that searches and renders bridge inventory records."""

    SUPPORTED_CONTENT_TYPES: ClassVar[list[str]] = ["text/plain"]

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._session_service = InMemorySessionService()
        self._memory_service = InMemoryMemoryService()
        self._artifact_service = InMemoryArtifactService()
        self._schema_managers = {
            VERSION_0_9: self._build_schema_manager(VERSION_0_9),
            VERSION_0_8: self._build_schema_manager(VERSION_0_8),
        }
        self._runner = self._build_runner()
        self._agent_card = self._build_agent_card()

    @property
    def agent_card(self) -> AgentCard:
        return self._agent_card

    def get_runner(self) -> Runner:
        return self._runner

    def get_schema_manager(self, version: str | None) -> A2uiSchemaManager | None:
        return self._schema_managers.get(version) if version else None

    def _build_schema_manager(self, version: str) -> A2uiSchemaManager:
        examples_path = os.path.join(_APP_DIR, "examples", "bridge_map_catalog", version)

        if version == VERSION_0_8:
            return A2uiSchemaManager(
                version=version,
                catalogs=[
                    CatalogConfig(
                        name="bridge_map",
                        provider=FileSystemCatalogProvider(CATALOG_DEFINITION_V0_8),
                        examples_path=examples_path,
                    ),
                    BasicCatalog.get_config(version=version),
                ],
                accepts_inline_catalogs=True,
                schema_modifiers=[remove_strict_validation],
            )

        return A2uiSchemaManager(
            version=version,
            catalogs=[
                CatalogConfig(
                    name="bridge_map",
                    provider=_MergedBasicCatalogProvider(CATALOG_DEFINITION_V0_9),
                    examples_path=examples_path,
                ),
                BasicCatalog.get_config(version=version, examples_path=examples_path),
            ],
            accepts_inline_catalogs=True,
            schema_modifiers=[remove_strict_validation],
        )

    def _build_agent_card(self) -> AgentCard:
        extensions = [
            get_a2ui_agent_extension(
                version,
                manager.accepts_inline_catalogs,
                manager.supported_catalog_ids,
            )
            for version, manager in self._schema_managers.items()
        ]
        return AgentCard(
            name="Bridge Inventory Agent",
            description="Searches BigQuery bridge/map tables and displays results with maps.",
            url=self.base_url,
            version="1.0.0",
            default_input_modes=self.SUPPORTED_CONTENT_TYPES,
            default_output_modes=self.SUPPORTED_CONTENT_TYPES,
            capabilities=AgentCapabilities(streaming=True, extensions=extensions),
            skills=[
                AgentSkill(
                    id="search_bridge_inventory",
                    name="Search Bridge Inventory",
                    description="Search configured bridge/map records and display their details and map.",
                    tags=["bridge", "inventory", "map", "bigquery"],
                    examples=[
                        "Show bridges in county 001.",
                        "Find bridge structure 1234567.",
                        "Show bridges crossing a creek.",
                    ],
                )
            ],
        )

    def _build_runner(self) -> Runner:
        instruction = f"{ROLE_DESCRIPTION}\n{WORKFLOW_DESCRIPTION}"
        llm_agent = LlmAgent(
            model=Gemini(
                model=DEFAULT_MODEL,
                retry_options=types.HttpRetryOptions(attempts=3),
            ),
            name="a2ui_bridge_map",
            description="Bridge Inventory Agent using BigQuery and Google Maps",
            instruction=instruction,
            tools=[search_bridges],
        )
        return Runner(
            app_name="a2ui_bridge_map",
            agent=llm_agent,
            artifact_service=self._artifact_service,
            session_service=self._session_service,
            memory_service=self._memory_service,
        )
