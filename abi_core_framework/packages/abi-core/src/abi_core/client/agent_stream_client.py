"""Low-level HTTP/SSE client for an ABI agent's web interface.

One implementation of session handling + SSE parsing, shared by every UI
(Chainlit, the TUI, future ones) instead of each reimplementing it. Extracted
from abi_core.ui.chainlit_app after abi_core.tui.services.OrchestratorClient
was found to have grown a second, session-less copy of the same logic.
"""

import ast
import json
from typing import Any, AsyncIterator, Optional

import httpx

from abi_core.common.utils import abi_logging


def parse_agent_message(msg: Any) -> dict:
    """Parse an SSE 'message' payload into a dict, safely.

    The stream is JSON, but the inner ``message`` can arrive as a JSON object
    or as a Python-dict string (``{'response_type': 'text', ...}``) depending
    on how the agent serialized it. Try JSON first, then ``ast.literal_eval``
    (safe — never executes code, unlike ``eval``).
    """
    if isinstance(msg, dict):
        return msg
    if not isinstance(msg, str):
        return {"content": str(msg)}
    try:
        return json.loads(msg)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        parsed = ast.literal_eval(msg)
        return parsed if isinstance(parsed, dict) else {"content": str(msg)}
    except (ValueError, SyntaxError):
        return {"content": msg}


class AgentStreamClient:
    """One instance per conversation — holds a session token and streams
    queries to an agent's /stream endpoint.

    No dependency on any UI framework: callers decide how to render the
    events this yields (status/text/data/input_required/error, each with
    optional meta — the same shape AgentResponse produces server-side).
    """

    def __init__(self, agent_url: str):
        self.agent_url = agent_url.rstrip("/")
        self._token: Optional[str] = None

    async def ensure_session(self) -> Optional[str]:
        """Start a session once and cache its token for this instance.

        Returns the bearer token, or ``None`` if the agent doesn't expose
        ``/session/start`` (older agents) or the call failed — in which case
        callers fall back to a tokenless request (a fresh anonymous session
        per message, no multi-turn continuity).
        """
        if self._token:
            return self._token
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.agent_url}/session/start", json={})
                if resp.status_code == 200:
                    self._token = resp.json().get("session_token")
                    return self._token
                abi_logging(
                    f"[⚠️] /session/start returned {resp.status_code}: {resp.text[:200]}",
                    level="warning",
                )
        except Exception as e:
            abi_logging(f"[⚠️] /session/start failed: {e}", level="warning")
        return None

    async def stream(self, query: str) -> AsyncIterator[dict]:
        """Send `query` to /stream and yield decoded AgentResponse-shaped
        events: {"response_type": ..., "content": ..., "meta": {...}}.

        Connection/parse failures are surfaced as a single
        {"response_type": "error", "content": "..."} event rather than
        raising — callers can treat every yielded item the same way.
        """
        token = await self.ensure_session()
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                try:
                    async with client.stream(
                        "POST",
                        f"{self.agent_url}/stream",
                        json={"query": query},
                        headers=headers,
                    ) as response:
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            raw = line[6:].strip()
                            if not raw or raw == "{}":
                                continue
                            try:
                                data = json.loads(raw)
                            except json.JSONDecodeError:
                                continue

                            parsed = parse_agent_message(data.get("message", ""))
                            if parsed:
                                yield parsed
                except (RuntimeError, GeneratorExit):
                    pass  # Stream closed by client — ignore
        except httpx.ConnectError:
            yield {
                "response_type": "error",
                "content": f"Cannot connect to the agent at {self.agent_url}. Is it running?",
            }
        except Exception as e:
            yield {"response_type": "error", "content": str(e)}
