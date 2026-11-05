"""Extension points of the Chat UI.

A project adds its own pieces to the Chat UI process without forking it:
``ABI_UI_EXTENSIONS`` lists Python modules (comma-separated); each exposes
``register(ui)`` and declares, through ``ui``, its routes, composer commands,
starters and chat hooks. A module that fails to import or register is
logged and skipped: a broken extension never stops the chat.

Spec: .abi/specs/not-implemented/ui-extensions.md
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib
import os
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable, List, Optional, Sequence, Tuple

from abi_core.common.utils import abi_logging

_CSRF_TTL_S = 3600
# After a resume Chainlit sends the thread to the page after on_chat_resume
# returns; a hook that posts a message waits for it.
RESUME_DELAY_S = 1.0


@dataclass
class _Command:
    id: str
    description: str
    icon: str
    handler: Callable[[Any], Awaitable[None]]
    button: bool = True


@dataclass
class _Registry:
    commands: List[_Command] = field(default_factory=list)
    on_chat_start: List[Callable[[], Awaitable[None]]] = field(default_factory=list)
    on_chat_resume: List[Callable[[dict], Awaitable[None]]] = field(default_factory=list)
    on_message: List[Callable[[Any], Awaitable[bool]]] = field(default_factory=list)
    starters: List[Tuple[str, str, Optional[str]]] = field(default_factory=list)


class UIExtensions:
    """What ``register(ui)`` receives."""

    def __init__(self, app=None):
        self._app = app
        self.registry = _Registry()

    # ── HTTP routes ───────────────────────────────────────────────────

    def _server(self):
        if self._app is None:
            from chainlit.server import app
            self._app = app
        return self._app

    def route(self, method: str, path: str, **kwargs):
        """Decorator for an HTTP route on Chainlit's server, placed before its
        catch-all route (which would otherwise answer with the SPA's page).

        A route is not protected by itself: depend on ``ui.require_user``.
        Its handler's errors are answered with a plain 500 and logged as the
        route and the exception type only: never the request body, headers or
        a traceback (a credentials form posts secrets)."""
        app = self._server()

        def decorator(handler):
            @wraps(handler)
            async def guarded(*args, **kw):
                from fastapi import HTTPException
                try:
                    return await handler(*args, **kw)
                except HTTPException:
                    raise
                except Exception as e:  # noqa: BLE001 — logged without content
                    abi_logging(f"[❌] UI extension route {method.upper()} {path} failed: {type(e).__name__}",
                                level="error")
                    raise HTTPException(status_code=500, detail="Internal error")

            catch_all = next((r for r in app.router.routes if hasattr(r, "original_router")), None)
            if catch_all is not None:
                app.router.routes.remove(catch_all)
            try:
                app.add_api_route(path, guarded, methods=[method.upper()], **kwargs)
            finally:
                if catch_all is not None:
                    app.router.routes.append(catch_all)
            return handler
        return decorator

    @property
    def require_user(self):
        """FastAPI dependency: the logged-in Chainlit user, or 401.

        Not Chainlit's get_current_user alone: without login configured it
        returns None instead of refusing, and the route would be open."""
        from chainlit.auth import get_current_user
        from fastapi import Depends, HTTPException

        async def _require(user=Depends(get_current_user)):
            if user is None:
                raise HTTPException(status_code=401, detail="Login required")
            return user
        return _require

    # ── CSRF for session-cookie POSTs ─────────────────────────────────

    @staticmethod
    def _csrf_key() -> bytes:
        key = os.getenv("CHAINLIT_AUTH_SECRET", "")
        if not key:
            raise RuntimeError("CHAINLIT_AUTH_SECRET is required for CSRF tokens")
        return key.encode()

    def csrf_token(self, user_id: str, now: Optional[float] = None) -> str:
        """A token bound to the user and the time, to embed in a form."""
        ts = str(int(now if now is not None else time.time()))
        sig = hmac.new(self._csrf_key(), f"{user_id}:{ts}".encode(), hashlib.sha256).hexdigest()
        return f"{ts}.{sig}"

    def verify_csrf(self, user_id: str, token: str, now: Optional[float] = None) -> bool:
        try:
            ts, sig = (token or "").split(".", 1)
            age = (now if now is not None else time.time()) - int(ts)
        except ValueError:
            return False
        if not 0 <= age <= _CSRF_TTL_S:
            return False
        expected = hmac.new(self._csrf_key(), f"{user_id}:{ts}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    def header_link(self, name: str, url: str, icon_url: str, display_name: Optional[str] = None,
                    target: str = "_self") -> None:
        """A link in the chat header that exists only while the extension is
        loaded (a link in config.toml would point at a missing page when the
        extension is off)."""
        from chainlit.config import HeaderLink, config
        links = list(config.ui.header_links or [])
        if any(link.name == name for link in links):
            return
        links.append(HeaderLink(name=name, url=url, icon_url=icon_url, display_name=display_name, target=target))
        config.ui.header_links = links

    # ── Chat ──────────────────────────────────────────────────────────

    def command(self, id: str, description: str, icon: str, handler, button: bool = True) -> None:
        """A composer command; a message sent with it goes to ``handler``."""
        self.registry.commands.append(_Command(id, description, icon, handler, button))

    def starter(self, label: str, message: str, icon: Optional[str] = None) -> None:
        """A starter on the empty chat."""
        self.registry.starters.append((label, message, icon))

    def on_chat_start(self, fn):
        self.registry.on_chat_start.append(fn)
        return fn

    def on_chat_resume(self, fn):
        """Runs when a conversation is resumed, after its thread is on the page."""
        self.registry.on_chat_resume.append(fn)
        return fn

    def on_message(self, fn):
        """Runs before a message goes to the agent; returning True keeps it
        from the agent (e.g. attachments for an open form)."""
        self.registry.on_message.append(fn)
        return fn

    # ── Identity ──────────────────────────────────────────────────────

    def current_user(self):
        """The session's user, or None (outside a chat session too)."""
        from chainlit.context import context_var
        ctx = context_var.get(None)
        return getattr(getattr(ctx, "session", None), "user", None)

    def identity_chain(self, secret_env: str, user_id: Optional[str] = None,
                       extra: Sequence[Tuple[str, str]] = ()) -> Optional[list]:
        """The user's HMAC identity chain sealed with ``secret_env``.

        In a chat it is the session's user (and thread). From an HTTP route
        (no chat session), pass ``user_id`` from ``require_user``. ``extra``
        adds ids after them (e.g. ``("workflow_id", ...)``). The role link
        comes last when the user is an admin. None without the secret or a
        user."""
        secret = os.getenv(secret_env)
        if not secret:
            return None
        from abi_core.security.identity_chain import build_chain
        user = self.current_user()
        uid = user_id or getattr(user, "id", None)
        if not uid:
            return None
        ids = [("user_id", uid)]
        if user_id is None:
            from chainlit.context import context_var
            thread_id = getattr(getattr(context_var.get(None), "session", None), "thread_id", None)
            if thread_id:
                ids.append(("thread_id", thread_id))
        ids.extend(extra)
        if (getattr(user, "metadata", None) or {}).get("is_admin") and (user_id is None or user_id == getattr(user, "id", None)):
            ids.append(("role", "admin"))
        return build_chain(secret, ids)


ui = UIExtensions()


def load(names: Optional[str] = None) -> List[str]:
    """Import every module in ABI_UI_EXTENSIONS and call its register(ui).
    Returns the ones that loaded."""
    loaded = []
    for name in [n.strip() for n in (names if names is not None else os.getenv("ABI_UI_EXTENSIONS", "")).split(",") if n.strip()]:
        try:
            importlib.import_module(name).register(ui)
            loaded.append(name)
            abi_logging(f"[🔌] UI extension loaded: {name}")
        except Exception as e:  # noqa: BLE001 — the chat runs without it
            abi_logging(f"[⚠️] UI extension {name} not loaded: {type(e).__name__}: {e}", level="warning")
    return loaded


async def _run_safely(fn, *args) -> None:
    try:
        await fn(*args)
    except Exception as e:  # noqa: BLE001
        abi_logging(f"[⚠️] UI extension hook {getattr(fn, '__name__', fn)} failed: {type(e).__name__}", level="warning")


async def run_chat_start() -> None:
    """Publish the commands, then run the start hooks in the background
    (asyncio tasks copy the session context, so a hook can send messages)."""
    if ui.registry.commands:
        from chainlit.context import context
        await context.emitter.set_commands([
            {"id": c.id, "description": c.description, "icon": c.icon, "button": c.button}
            for c in ui.registry.commands])
    for fn in ui.registry.on_chat_start:
        asyncio.create_task(_run_safely(fn))


async def run_chat_resume(thread: dict) -> None:
    if ui.registry.commands:
        from chainlit.context import context
        await context.emitter.set_commands([
            {"id": c.id, "description": c.description, "icon": c.icon, "button": c.button}
            for c in ui.registry.commands])

    async def later(fn):
        await asyncio.sleep(RESUME_DELAY_S)
        await _run_safely(fn, thread)

    for fn in ui.registry.on_chat_resume:
        asyncio.create_task(later(fn))


async def handle_message(message) -> bool:
    """True when an extension took the message (a command, or a hook that
    claimed it); False to send it to the agent."""
    command = getattr(message, "command", None)
    if command:
        for c in ui.registry.commands:
            if c.id == command:
                await c.handler(message)
                return True
    for fn in ui.registry.on_message:
        try:
            if await fn(message):
                return True
        except Exception as e:  # noqa: BLE001 — the message still reaches the agent
            abi_logging(f"[⚠️] UI extension on_message failed: {type(e).__name__}", level="warning")
    return False
