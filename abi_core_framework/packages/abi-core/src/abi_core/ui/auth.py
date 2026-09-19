"""OAuth login (Google) + persistent sessions + invite-link registration.

Implements two specs together (they share the same `@cl.oauth_callback`):
    .abi/specs/not-implemented/chainlit-oauth-login-session-continuity.md
    .abi/specs/not-implemented/chainlit-invite-link-registration.md

Imported by chainlit_app.py purely for its decorator side effects
(``@cl.oauth_callback``, ``@cl.data_layer``, ``@cl.on_chat_resume``) and to
register the extra FastAPI routes/exception handler on Chainlit's own app.

Everything here is a no-op if ``DATABASE_URL`` isn't set — chatui keeps working
in the old anonymous, tokenless mode for local dev without Postgres. OAuth
itself only activates if Chainlit finds ``OAUTH_GOOGLE_CLIENT_ID``/`_SECRET`
set (its own mechanism, not ours).
"""

import json
import os
import secrets
import smtplib
from email.message import EmailMessage
from typing import Optional

import chainlit as cl
import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from fastapi.exception_handlers import http_exception_handler

from abi_core.common.utils import abi_logging

DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql+asyncpg://user:pass@host/db

_engine: Optional[AsyncEngine] = None


def _get_engine() -> Optional[AsyncEngine]:
    global _engine
    if _engine is None and DATABASE_URL:
        _engine = create_async_engine(DATABASE_URL)
    return _engine


# ── Schema ──────────────────────────────────────────────────────────────
#
# Two sets of tables in the same database:
#
# 1. Chainlit's own tables (users/threads/steps/feedbacks/elements) — no
#    schema ships in the installed `chainlit` package (confirmed: no .sql
#    file in site-packages). Derived here directly from the field names
#    `SQLAlchemyDataLayer` reads/writes (chainlit/types.py, step.py,
#    element.py, user.py — read at v2.11.1, the version live in
#    abi-swarm-chatui when this was written) — not from memory/assumption.
#    Verify against a newer Chainlit's actual queries if this drifts.
# 2. `invites`/`waiting_list` — ours, designed in the specs above.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT UNIQUE NOT NULL,
    "createdAt" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" TEXT REFERENCES users("id") ON DELETE CASCADE,
    "userIdentifier" TEXT,
    "tags" TEXT[],
    "metadata" JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "type" TEXT,
    "threadId" TEXT REFERENCES threads("id") ON DELETE CASCADE,
    "parentId" TEXT,
    "command" TEXT,
    "modes" JSONB,
    "streaming" BOOLEAN,
    "waitForAnswer" BOOLEAN,
    "isError" BOOLEAN,
    "metadata" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "tags" TEXT[],
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" JSONB,
    "showInput" TEXT,
    "defaultOpen" BOOLEAN,
    "autoCollapse" BOOLEAN,
    "language" TEXT,
    "icon" TEXT
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "forId" TEXT NOT NULL,
    "threadId" TEXT REFERENCES threads("id") ON DELETE CASCADE,
    "value" INT NOT NULL,
    "comment" TEXT
);

CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "threadId" TEXT REFERENCES threads("id") ON DELETE CASCADE,
    "type" TEXT,
    "chainlitKey" TEXT,
    "url" TEXT,
    "objectKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "size" TEXT,
    "language" TEXT,
    "page" INT,
    "props" JSONB,
    "autoPlay" BOOLEAN,
    "playerConfig" JSONB,
    "forId" TEXT,
    "mime" TEXT
);

CREATE TABLE IF NOT EXISTS invites (
    token TEXT PRIMARY KEY,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    used BOOLEAN NOT NULL DEFAULT false,
    used_by TEXT,
    used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS waiting_list (
    email TEXT PRIMARY KEY,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notified BOOLEAN NOT NULL DEFAULT false
);
"""

_schema_ready = False


async def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    engine = _get_engine()
    if engine is None:
        return
    async with engine.begin() as conn:
        for statement in _SCHEMA.strip().split(";"):
            statement = statement.strip()
            if statement:
                await conn.execute(sa.text(statement))
    _schema_ready = True


# ── Invite / admin / waiting-list helpers ──────────────────────────────


async def _no_users_exist_yet() -> bool:
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(sa.text("SELECT COUNT(*) FROM users"))
        return result.scalar() == 0


async def _get_user_metadata(email: str) -> Optional[dict]:
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text('SELECT "metadata" FROM users WHERE "identifier" = :email'),
            {"email": email},
        )
        row = result.first()
    if row is None:
        return None
    raw = row[0]
    # asyncpg's jsonb decoding through raw sa.text() isn't guaranteed to
    # come back as a dict (depends on codec registration) — handle both.
    return json.loads(raw) if isinstance(raw, str) else raw


async def claim_one_unused_invite(email: str) -> bool:
    """Atomically consume one unused invite, if any exist. See
    chainlit-invite-link-registration.md — the link is generic (not tied to
    a specific email), so this claims whichever is available, not "the one
    tied to the link that was clicked" (no way to know that — see spec)."""
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text(
                """
                UPDATE invites SET used = true, used_by = :email, used_at = now()
                WHERE token = (
                    SELECT token FROM invites WHERE used = false
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                )
                RETURNING token
                """
            ),
            {"email": email},
        )
        return result.first() is not None


async def create_invites(created_by: Optional[str], count: int = 1) -> list[str]:
    engine = _get_engine()
    tokens = [secrets.token_urlsafe(24) for _ in range(count)]
    async with engine.begin() as conn:
        for token in tokens:
            await conn.execute(
                sa.text(
                    "INSERT INTO invites (token, created_by) VALUES (:token, :created_by)"
                ),
                {"token": token, "created_by": created_by},
            )
    return tokens


async def has_generated_invite(email: str) -> bool:
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text("SELECT 1 FROM invites WHERE created_by = :email LIMIT 1"),
            {"email": email},
        )
        return result.first() is not None


async def invite_is_valid(token: str) -> bool:
    engine = _get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.text("SELECT used FROM invites WHERE token = :token"),
            {"token": token},
        )
        row = result.first()
        return row is not None and row[0] is False


async def add_to_waiting_list(email: str) -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO waiting_list (email) VALUES (:email) "
                "ON CONFLICT (email) DO NOTHING"
            ),
            {"email": email},
        )
    _notify_admin_of_waiting_list(email)


def _notify_admin_of_waiting_list(email: str) -> None:
    """Best-effort email to the admin — never blocks/raises into the caller.
    SMTP creds not configured → logs a warning and skips, doesn't crash the
    waiting-list signup itself."""
    host = os.getenv("SMTP_HOST")
    admin_email = os.getenv("ADMIN_NOTIFICATION_EMAIL")
    if not host or not admin_email:
        abi_logging(
            "[⚠️] SMTP_HOST/ADMIN_NOTIFICATION_EMAIL not set — skipping waiting-list "
            f"notification for {email}",
            level="warning",
        )
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = "ABI Swarm — nueva solicitud de acceso"
        msg["From"] = os.getenv("SMTP_FROM", admin_email)
        msg["To"] = admin_email
        msg.set_content(f"{email} pidió acceso al swarm y quedó en la waiting list.")

        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASSWORD")
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    except Exception as e:  # noqa: BLE001 — never let a notification failure break signup
        abi_logging(f"[⚠️] Could not send waiting-list notification email: {e}", level="warning")


# ── Data layer ──────────────────────────────────────────────────────────

if DATABASE_URL:

    @cl.data_layer
    def get_data_layer():
        from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

        storage_provider = None
        # Reuses the swarm's existing MinIO (S3-compatible) — same
        # ARTIFACT_* convention already used by builder/orchestrator/planner
        # for agent artifacts, just a separate bucket for chat thread
        # elements (images, files) so the two don't mix. Without this,
        # SQLAlchemyDataLayer.create_element() fails with "No
        # blob_storage_client is configured!" for any element in a thread.
        artifact_endpoint = os.getenv("ARTIFACT_ENDPOINT")
        if artifact_endpoint:
            from chainlit.data.storage_clients.s3 import S3StorageClient

            storage_provider = S3StorageClient(
                bucket=os.getenv("CHAINLIT_ELEMENTS_BUCKET", "abi-chainlit-elements"),
                endpoint_url=artifact_endpoint,
                aws_access_key_id=os.getenv("ARTIFACT_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("ARTIFACT_SECRET_KEY"),
            )

        return SQLAlchemyDataLayer(conninfo=DATABASE_URL, storage_provider=storage_provider)


# ── OAuth callback ──────────────────────────────────────────────────────


@cl.oauth_callback
async def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: dict,
    default_app_user: cl.User,
    id_token: Optional[str] = None,
) -> Optional[cl.User]:
    if not DATABASE_URL:
        # No Postgres configured — auth can't be enforced without persistent
        # state (invites/users). Fail closed rather than silently open.
        abi_logging("[⚠️] OAuth callback fired but DATABASE_URL is not set — rejecting", level="warning")
        return None

    await _ensure_schema()

    email = raw_user_data.get("email")
    if not email:
        return None

    existing_metadata = await _get_user_metadata(email)
    if existing_metadata is not None:
        # Chainlit's own _authenticate_user calls create_user() on EVERY
        # login (not just the first), and create_user() overwrites the
        # user's stored metadata with whatever we return here — so we have
        # to carry the existing metadata (is_admin, etc.) forward, or a
        # second login would silently wipe it.
        default_app_user.metadata = existing_metadata
        return default_app_user

    if await _no_users_exist_yet():
        # Bootstrap: the very first registration never needs an invite and
        # becomes admin. See chainlit-invite-link-registration.md.
        default_app_user.metadata["is_admin"] = True
        return default_app_user

    if await claim_one_unused_invite(email):
        return default_app_user

    # No user, no invite available — reject. The exception handler below
    # turns Chainlit's generic 401 into a redirect to our own /waiting-list
    # form (which is what actually records the email + notifies the admin).
    return None


# ── Session-continuity bridge (chainlit-oauth-login-session-continuity.md) ─


@cl.on_chat_resume
async def on_chat_resume(thread: dict) -> None:
    from abi_core.client.agent_stream_client import AgentStreamClient

    agent_url = os.getenv("ABI_AGENT_URL", "http://localhost:8083")
    token = (thread.get("metadata") or {}).get("abi_session_token")
    client = AgentStreamClient(agent_url, token=token)
    cl.user_session.set("abi_stream_client", client)


# ── Custom routes: invite links, waiting-list form, admin page ─────────


def _register_routes() -> None:
    """Registers extra routes + the exception-handler redirect on Chainlit's
    own FastAPI app. Called once at import time (chainlit_app.py imports
    this module for its side effects) — a no-op without DATABASE_URL."""
    if not DATABASE_URL:
        return

    from chainlit.server import app as chainlit_asgi_app

    # Chainlit's own routes (including a catch-all `/{full_path:path}` that
    # serves the SPA's index.html for anything unmatched) are added via
    # `app.include_router(router)` at import time — before this module ever
    # loads — which wraps them in an internal `_IncludedRouter` object
    # sitting at a fixed position in `app.router.routes` (confirmed live by
    # inspecting the running app: it's not a plain `Route`, `.path` is
    # `None` on the wrapper itself, so matching by literal path string finds
    # nothing). Routes we add normally get appended AFTER that wrapper, and
    # since the wrapper's own catch-all matches any path, it shadows ours —
    # confirmed live (curling a newly added route returned Chainlit's
    # index.html, identical to a route that doesn't exist at all). Pull the
    # whole wrapper out, register ours, then put it back at the end so it's
    # still tried (and still works — /health etc. live inside it too) for
    # anything none of ours matched.
    _catch_all = None
    for _route in list(chainlit_asgi_app.router.routes):
        if hasattr(_route, "original_router"):
            _catch_all = _route
            chainlit_asgi_app.router.routes.remove(_route)
            break

    @chainlit_asgi_app.exception_handler(HTTPException)
    async def _redirect_credentialssignin(request: Request, exc: HTTPException):
        if exc.status_code == 401 and exc.detail == "credentialssignin":
            return RedirectResponse("/waiting-list")
        return await http_exception_handler(request, exc)

    @chainlit_asgi_app.get("/invite/{token}")
    async def invite_landing(token: str):
        await _ensure_schema()
        if await invite_is_valid(token):
            return RedirectResponse("/auth/oauth/google")
        return HTMLResponse(
            "<h1>Este link de invitación ya se usó o no es válido.</h1>"
            '<p><a href="/waiting-list">Sumate a la waiting list</a></p>',
            status_code=400,
        )

    @chainlit_asgi_app.get("/waiting-list")
    async def waiting_list_form():
        return HTMLResponse(
            """
            <html><body style="font-family: sans-serif; max-width: 480px; margin: 80px auto;">
              <h1>Acceso por invitación</h1>
              <p>No tenés una invitación disponible ahora mismo. Dejanos tu email y
                 te avisamos apenas tengas acceso.</p>
              <form method="post" action="/waiting-list">
                <input type="email" name="email" placeholder="tu@email.com" required
                       style="padding:8px; width:100%; box-sizing:border-box;" />
                <button type="submit" style="margin-top:12px; padding:8px 16px;">
                  Sumarme a la waiting list
                </button>
              </form>
            </body></html>
            """
        )

    @chainlit_asgi_app.post("/waiting-list")
    async def waiting_list_submit(request: Request):
        form = await request.form()
        email = (form.get("email") or "").strip()
        if not email:
            return PlainTextResponse("Email requerido", status_code=400)
        await _ensure_schema()
        await add_to_waiting_list(email)
        return HTMLResponse(
            "<h1>¡Listo!</h1><p>Te vamos a avisar apenas tengas acceso.</p>"
        )

    from chainlit.auth import get_current_user

    def _render_invite_rows(rows) -> str:
        if not rows:
            return "<p><em>Ninguna todavía.</em></p>"
        items = "".join(
            f"<li>{r.token[:12]}… — {'usada por ' + r.used_by if r.used else 'sin usar'}</li>"
            for r in rows
        )
        return f"<ul>{items}</ul>"

    @chainlit_asgi_app.get("/admin/invites")
    async def admin_invites_page(current_user=Depends(get_current_user)):
        if not current_user or not current_user.metadata.get("is_admin"):
            raise HTTPException(status_code=403, detail="Solo el admin puede ver esta página")

        await _ensure_schema()
        engine = _get_engine()
        async with engine.begin() as conn:
            invites = (await conn.execute(sa.text("SELECT token, used, used_by FROM invites ORDER BY created_at DESC"))).all()
            waiting = (await conn.execute(sa.text("SELECT email, requested_at FROM waiting_list ORDER BY requested_at DESC"))).all()

        base_url = os.getenv("CHAINLIT_URL", "")
        invite_links = "".join(
            f"<li>{base_url}/invite/{r.token}</li>" for r in invites if not r.used
        )
        waiting_rows = "".join(f"<li>{r.email}</li>" for r in waiting) or "<p><em>Vacía.</em></p>"

        return HTMLResponse(f"""
            <html><body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
              <h1>Invitaciones</h1>
              <form method="post" action="/admin/invites">
                <label>Cantidad: <input type="number" name="count" value="5" min="1" max="20" /></label>
                <button type="submit">Generar</button>
              </form>
              <h2>Links sin usar</h2>
              <ul>{invite_links or "<li><em>Ninguno.</em></li>"}</ul>
              <h2>Historial</h2>
              {_render_invite_rows(invites)}
              <h2>Waiting list</h2>
              {waiting_rows}
            </body></html>
        """)

    @chainlit_asgi_app.post("/admin/invites")
    async def admin_invites_generate(request: Request, current_user=Depends(get_current_user)):
        if not current_user or not current_user.metadata.get("is_admin"):
            raise HTTPException(status_code=403, detail="Solo el admin puede generar invitaciones")

        form = await request.form()
        try:
            count = max(1, min(20, int(form.get("count", 1))))
        except ValueError:
            count = 1
        await _ensure_schema()
        await create_invites(created_by=None, count=count)
        return RedirectResponse("/admin/invites", status_code=303)

    @chainlit_asgi_app.get("/invites/mine")
    async def my_invite_page(current_user=Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Login requerido")

        await _ensure_schema()
        email = current_user.identifier
        already = await has_generated_invite(email)
        base_url = os.getenv("CHAINLIT_URL", "")

        if not already:
            return HTMLResponse(f"""
                <html><body style="font-family: sans-serif; max-width: 480px; margin: 80px auto;">
                  <h1>Invitá a alguien</h1>
                  <form method="post" action="/invites/mine">
                    <button type="submit">Generar mi link de invitación</button>
                  </form>
                </body></html>
            """)

        engine = _get_engine()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    sa.text("SELECT token, used FROM invites WHERE created_by = :email LIMIT 1"),
                    {"email": email},
                )
            ).first()

        status = "ya fue usado" if row and row.used else "todavía sin usar"
        return HTMLResponse(f"""
            <html><body style="font-family: sans-serif; max-width: 480px; margin: 80px auto;">
              <h1>Tu link de invitación</h1>
              <p>{base_url}/invite/{row.token if row else ''}</p>
              <p><em>{status}</em></p>
            </body></html>
        """)

    @chainlit_asgi_app.post("/invites/mine")
    async def my_invite_generate(current_user=Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Login requerido")

        await _ensure_schema()
        email = current_user.identifier
        if not await has_generated_invite(email):
            await create_invites(created_by=email, count=1)
        return RedirectResponse("/invites/mine", status_code=303)

    if _catch_all is not None:
        chainlit_asgi_app.router.routes.append(_catch_all)
    else:
        # Didn't find the wrapper to reorder — likely a Chainlit internals
        # change. Not fatal (routes above still got added), but they may be
        # shadowed by whatever Chainlit does with unmatched paths now.
        abi_logging(
            "[⚠️] Could not find Chainlit's included router to reorder — "
            "custom routes (/waiting-list, /invite/*, /admin/*) may be "
            "shadowed. Chainlit internals likely changed since this was written.",
            level="warning",
        )


_register_routes()
