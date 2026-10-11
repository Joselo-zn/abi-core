"""
Fixes from the reviewer pipeline's live runs (2026-10-10):
Gemini's list content in the tool-calling stream, and A2A denials split
into policy decisions (not retried) and connection failures (retried).
"""

import asyncio
import types

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from abi_core.agent import llm_provider
from abi_core.common import abi_a2a


def test_stream_accepts_list_content_from_gemini():
    class FakeAgent:
        async def _gen(self):
            yield AIMessageChunk(content=[{"type": "text", "text": "Wrote ", "extras": {"signature": "x"}}]), {}
            yield ToolMessage(content="ok", tool_call_id="1"), {}
            yield AIMessageChunk(content=[{"type": "text", "text": "player.py"}]), {}

        def astream(self, *a, **k):
            return self._gen()

    out = asyncio.run(llm_provider._stream_agent_with_timeout(FakeAgent(), {}, {}, 5))
    assert out == "Wrote player.py"


@pytest.mark.parametrize("reason,expected", [
    ("Communication not allowed: a -> b", abi_a2a.A2APolicyDenied),
    ("Source or target agent not properly identified", abi_a2a.A2APolicyDenied),
    ("Validation error: All connection attempts failed", PermissionError),
    ("Guardian timeout", PermissionError),
    ("Guardian returned status 500", PermissionError),
])
def test_a2a_denial_kind(monkeypatch, reason, expected):
    class Validator:
        async def validate_a2a_access(self, **kw):
            return False, reason

    monkeypatch.setattr(abi_a2a, "get_validator", lambda: Validator())
    card = types.SimpleNamespace(name="a")

    async def call():
        async for _ in abi_a2a.agent_connection(card, card, {"message": {"parts": [{"text": "x"}]}}):
            pass

    with pytest.raises(PermissionError) as info:
        asyncio.run(call())
    assert type(info.value) is expected


@pytest.mark.parametrize("parts,expected", [
    ([{"text": "hello"}], ["hello"]),                 # documented example: no "kind"
    ([{"kind": "text", "text": "hello"}], ["hello"]),
    ([{"kind": "file", "uri": "x"}], []),
])
def test_agent_connection_text_parts(monkeypatch, parts, expected):
    """A message whose parts had no "kind" went out empty and the receiver
    rejected it ("Validation failed") — live 2026-10-10, every hand-off."""
    sent = []

    class Validator:
        async def validate_a2a_access(self, **kw):
            return True, None

    class Client:
        def send_message(self, request):
            sent.append(request.message)

            async def gen():
                if False:
                    yield None
            return gen()

    class Factory:
        def __init__(self, cfg):
            pass

        def create(self, card):
            return Client()

    monkeypatch.setattr(abi_a2a, "get_validator", lambda: Validator())
    monkeypatch.setattr(abi_a2a, "ClientFactory", Factory)
    monkeypatch.setattr(abi_a2a, "get_agent_url", lambda card: "http://x:1")
    card = types.SimpleNamespace(name="a")

    async def call():
        async for _ in abi_a2a.agent_connection(card, card, {"message": {"role": "user", "parts": parts}}):
            pass

    asyncio.run(call())
    assert [p.text for p in sent[0].parts] == expected
