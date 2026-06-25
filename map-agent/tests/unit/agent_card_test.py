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

"""Unit tests for agent card creation."""

from app.agent import BridgeInventoryAgent
from app.bridge_tools import search_map_records


def test_agent_card_has_required_fields():
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")
    card = agent.agent_card
    assert card.name == "Transportation Map Agent"
    assert card.description
    assert card.url == "http://localhost:8000"
    assert card.version


def test_agent_card_has_skills():
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")
    card = agent.agent_card
    assert card.skills
    assert len(card.skills) > 0
    skill = card.skills[0]
    assert skill.id == "search_transportation_map_records"
    assert skill.name
    assert skill.description
    assert skill.examples


def test_agent_card_has_capabilities():
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")
    card = agent.agent_card
    assert card.capabilities is not None
    assert card.capabilities.streaming is True


def test_agent_card_url():
    url = "https://example.com/my-agent"
    agent = BridgeInventoryAgent(base_url=url)
    card = agent.agent_card
    assert card.url == url


def test_agent_card_input_output_modes():
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")
    card = agent.agent_card
    assert "text/plain" in card.default_input_modes
    assert "text/plain" in card.default_output_modes


def test_agent_card_has_a2ui_extension():
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")
    card = agent.agent_card
    extensions = card.capabilities.extensions
    assert extensions is not None
    assert len(extensions) > 0
    a2ui_uris = [e.uri for e in extensions]
    assert any("a2ui" in uri for uri in a2ui_uris)


def test_agent_only_asks_model_to_call_small_search_tool():
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")
    llm_agent = agent.get_runner().agent

    assert llm_agent.tools == [search_map_records]
    assert "send_a2ui_json_to_client" not in llm_agent.instruction
    assert "Do not write A2UI JSON" in llm_agent.instruction
