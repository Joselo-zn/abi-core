"""What a model sees of an agent card: no host, model or auth.
Spec: .abi/specs/not-implemented/agent-identity-disclosure.md
"""

import asyncio
import json
from types import SimpleNamespace

from abi_core.common import semantic_tools
from abi_core.common.agent_card_loader import build_agent_card
from abi_core.common.semantic_tools import agent_card_for_model, tool_find_agent_for_model

CARD = {
    "id": "agent://planner", "name": "planner", "description": "Turns a request into tasks.",
    "url": "https://abi-swarm-planner-alpha-123.region.run.app", "version": "1.0.0",
    "capabilities": {"streaming": True}, "defaultInputModes": ["text"], "defaultOutputModes": ["text"],
    "skills": [{"id": "plan", "name": "Plan", "description": "Breaks work down.", "tags": ["plan"],
                "examples": ["build a game"]}],
    "llmConfig": {"provider": "gemini", "model": "gemini-3.6-flash"},
    "auth": {"method": "hmac"}, "metadata": {"internal": "x"},
}


def test_the_model_gets_only_what_the_agent_does():
    card, _ = build_agent_card(CARD)
    out = agent_card_for_model(card)
    assert out == {"name": "planner", "description": "Turns a request into tasks.",
                   "skills": [{"name": "Plan", "description": "Breaks work down."}]}
    text = json.dumps(out)
    for leak in ("run.app", "gemini", "hmac", "internal", "llmConfig", "url"):
        assert leak not in text
    assert agent_card_for_model(None) is None


def test_the_tool_the_model_calls_cuts_the_card(monkeypatch):
    card, _ = build_agent_card(CARD)

    async def ainvoke(args):
        return card

    monkeypatch.setattr(semantic_tools, "tool_find_agent", SimpleNamespace(ainvoke=ainvoke))
    assert tool_find_agent_for_model.name == "tool_find_agent"        # same name to the model
    out = asyncio.run(tool_find_agent_for_model.ainvoke({"query": "plan"}))
    assert "url" not in out and out["name"] == "planner"
