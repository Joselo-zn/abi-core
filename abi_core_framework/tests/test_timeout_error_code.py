"""A timeout reaches the client as English text plus an error code; the
Chainlit UI shows it in the user's language."""

import asyncio
import json
from types import SimpleNamespace

from abi_core.agent.agent import AbiAgent, HeartbeatTimeoutError
from abi_core.agent.agent_response import AgentResponse
from abi_core.client.agent_stream_client import parse_agent_message
from abi_core.common.utils import yield_chunk_data
from abi_core.ui.run_progress import error_message


async def _timeout_from_heartbeat():
    """Run the real _run_with_heartbeat with a coroutine slower than max_wait."""
    fake_self = SimpleNamespace(agent_name="t")
    try:
        async for _ in AbiAgent._run_with_heartbeat(
            fake_self, asyncio.sleep(5), "ctx", "task", "working", max_wait=0.2, interval=0.05,
        ):
            pass
    except HeartbeatTimeoutError as e:
        return e
    raise AssertionError("no timeout")


def test_timeout_is_english_and_coded():
    exc = asyncio.run(_timeout_from_heartbeat())
    assert exc.error_code == "timeout" and exc.max_wait == 0.2
    assert "taking longer than expected" in str(exc) and "tardando" not in str(exc)


def test_error_from_carries_the_code_and_plain_errors_dont():
    coded = AgentResponse.error_from(HeartbeatTimeoutError("slow", max_wait=180))
    assert coded["content"] == "slow" and coded["meta"] == {"error_code": "timeout", "max_wait": 180}
    plain = AgentResponse.error_from(ValueError("boom"))
    assert plain == AgentResponse.error("boom") and "meta" not in plain


def test_ui_shows_it_in_the_users_language_after_the_stream():
    response = AgentResponse.error_from(HeartbeatTimeoutError("slow", max_wait=180))

    async def over_the_wire():
        return [b async for b in yield_chunk_data(response)][0].decode()

    line = asyncio.run(over_the_wire())
    parsed = parse_agent_message(json.loads(line[len("data: "):])["message"])
    assert "más de 180s" in error_message("es-ES", parsed.get("meta"))
    assert "over 180s" in error_message("en-US", parsed.get("meta"))


def test_unknown_or_missing_code_keeps_the_generic_message():
    assert error_message("es", None) is None
    assert error_message("es", {"error_code": "other"}) is None
