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
            context_id = None
            token_resolved = False
            token = None

            # ── Identity chain (chatui hop) — see
            # .abi/specs/not-implemented/identity-chain-hmac-contract.md.
            # Authoritative when present: verify against the shared hop
            # secret and derive context_id deterministically from
            # (user_id, thread_id). No silent fallback on failure — a
            # present-but-invalid chain is rejected outright, never
            # downgraded to an anonymous session (that downgrade is exactly
            # what made the old token flow's failures ambiguous and hard to
            # trace — reproduced live 2026-09-26, root-caused to two browser
            # tabs each holding their own independent, individually-valid
            # opaque token with no shared identity between them).
            identity_chain = request.get("identity_chain")
            if identity_chain:
                from abi_core.security.identity_chain import derive_session_id, get_id, verify_chain

                hop_secret = os.getenv("HOP_SECRET_CHATUI_ORCHESTRATOR", "")
                if not hop_secret or not verify_chain(hop_secret, identity_chain):
                    raise HTTPException(status_code=401, detail="Invalid identity chain")
                user_id = get_id(identity_chain, "user_id")
                thread_id = get_id(identity_chain, "thread_id")
                if not user_id or not thread_id:
                    raise HTTPException(status_code=401, detail="Identity chain missing required ids")
                context_id = derive_session_id(user_id, thread_id)

            # ── Fallback: opaque session token (unchanged) — still the only
            # mechanism for callers that don't send an identity chain (the
            # TUI, or any future client not yet migrated). See
            # .abi/specs/implemented/session-management.md.
            if context_id is None:
                token = _extract_token(authorization)
                # Only meaningful when `token` was actually sent — tells the
                # caller "the token you sent didn't resolve, I fell back to an
                # anonymous session" so it can call /session/start again for its
                # NEXT message instead of silently reusing a dead token forever.
                if token:
                    session = await self.session_store.resolve(token)
                    if session is not None:
                        context_id = session.context_id
                        token_resolved = True
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

            headers = {
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
            if token and not token_resolved:
                headers["X-Session-Resolved"] = "false"

            return StreamingResponse(
                generate_response(),
                media_type="text/event-stream",
                headers=headers,
            )
