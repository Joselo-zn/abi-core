# web_interface.py
import os
import asyncio, json, time

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from abi_core.common.utils import abi_logging
from abi_core.common.utils import yield_chunk_data
from abi_core.session import SessionStore


def _extract_token(authorization: str | None) -> str | None:
    """Pull a bearer token out of an Authorization header, if present."""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip() or None


class OrchestratorWebinterface:
    """Web interface for the orchestrator with framework-managed sessions.

    Sessions are opt-in and backed by ``abi_core.session.SessionStore`` over the
    *same* backend the agent uses (``agent.session_backend``), so token →
    context_id resolution and the conversation context share one store. With the
    Redis backend this is LB/multi-pod safe: any pod resolves the same token.

    The ``context_id`` is generated in the backend (never trusted from the
    client), which fixes both spoofing and the shared ``web-session`` collision.

    Env:
        ABI_SESSION_REQUIRED  "true" → /stream rejects requests without a valid
                              token. Default "false" (dev): a missing/invalid
                              token falls back to an anonymous session.
    """

    def __init__(self, orchestrator_agent):
        self.orchestrator_agent = orchestrator_agent
        # Reuse the agent's backend so tokens and context share one store.
        self.session_store = SessionStore(getattr(orchestrator_agent, "session_backend", None))
        self.session_required = os.getenv("ABI_SESSION_REQUIRED", "false").lower() == "true"
        self.app = FastAPI()
        self.setup_routes()

    def setup_routes(self):
        @self.app.post("/session/start")
        async def session_start(request: dict | None = None):
            metadata = (request or {}).get("metadata") if isinstance(request, dict) else None
            session = await self.session_store.create_session(metadata=metadata or {})
            return {
                "session_token": session.tokens[0],
                "expires_at": session.expires_at,
            }

        @self.app.post("/session/rotate")
        async def session_rotate(authorization: str | None = Header(default=None)):
            token = _extract_token(authorization)
            if not token:
                raise HTTPException(status_code=401, detail="Missing session token")
            new_token = await self.session_store.rotate(token)
            if not new_token:
                raise HTTPException(status_code=401, detail="Invalid or expired session token")
            return {"session_token": new_token}

        @self.app.post("/session/end")
        async def session_end(authorization: str | None = Header(default=None)):
            token = _extract_token(authorization)
            if not token:
                raise HTTPException(status_code=401, detail="Missing session token")
            destroyed = await self.session_store.destroy(token)
            return {"destroyed": destroyed}

        @self.app.post("/stream")
        async def stream_query(
            request: dict,
            authorization: str | None = Header(default=None),
        ):
            query = request.get("query")

            # ── Resolve session → context_id (backend-generated, opaque) ──
            token = _extract_token(authorization)
            context_id = None
            if token:
                session = await self.session_store.resolve(token)
                if session is not None:
                    context_id = session.context_id
                elif self.session_required:
                    raise HTTPException(status_code=401, detail="Invalid or expired session token")

            if context_id is None:
                if self.session_required:
                    raise HTTPException(status_code=401, detail="Session token required")
                # Backward-compat: anonymous session in the SAME backend (unique
                # context_id per request → no shared "web-session" collision).
                session = await self.session_store.create_session(metadata={"anonymous": True})
                context_id = session.context_id

            task_id = request.get("task_id", f"task-{int(time.time())}")

            async def generate_response():
                yield b"event: ping\ndata: {}\n\n"
                try:
                    async for chunk in self.orchestrator_agent.stream(
                        query=query, context_id=context_id, task_id=task_id
                    ):
                        async for sse_bytes in yield_chunk_data(chunk):
                            yield sse_bytes

                    yield b"event: done\ndata: {}\n\n"
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    abi_logging(f"Error en SSE generate_response: {e}", level="error")
                    yield (f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n").encode()
                    await asyncio.sleep(0.05)

            return StreamingResponse(
                generate_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
