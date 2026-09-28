"""ABI-Core Chainlit Chat Interface.

A thin renderer over abi_core.client.AgentStreamClient — it opens a
framework-managed session so multi-turn conversations stay stable (a clarifying
question and its answer land in the same context), and streams status/result
updates into the Chainlit UI. Plan-confirmation replies (approve/reject/modify)
are rendered as real action buttons when the agent emits
``meta.action_type == "plan_confirmation"``.

This is the single, canonical implementation — run it with:
    abi-core ui chainlit --url http://localhost:8083

or directly:
    ABI_AGENT_URL=http://localhost:8083 chainlit run \
        $(python -c "import abi_core.ui.chainlit_app as m; print(m.__file__)")

No project needs its own copy of this file — `abi-core add chainlit` points a
Docker service at it instead of generating one.
"""

import asyncio
import importlib.resources
import json
import os
import shutil
import smtplib
import warnings
from email.message import EmailMessage
from pathlib import Path

import chainlit as cl

from abi_core.client.agent_stream_client import AgentStreamClient

# Suppress httpcore async generator cleanup warnings (cosmetic, non-blocking)
warnings.filterwarnings("ignore", message=".*async generator ignored GeneratorExit.*")

# Opt-in OAuth login + invite-link registration — imported only when a
# provider is actually configured, because `@cl.oauth_callback` raises at
# decoration time if no OAuth provider env vars are set (chainlit's own
# validation, not ours) — importing this unconditionally would break every
# abi-core deployment that doesn't use OAuth. See
# .abi/specs/not-implemented/chainlit-oauth-login-session-continuity.md and
# .abi/specs/not-implemented/chainlit-invite-link-registration.md.
if os.getenv("OAUTH_GOOGLE_CLIENT_ID"):
    import abi_core.ui.auth  # noqa: F401 — side effects only


def _install_bundled_elements() -> None:
    """Copy abi_core's bundled .jsx custom elements into ./public/elements/
    (Chainlit's convention-based discovery dir — see
    chainlit.config.public_dir) if missing or changed. Runs once at import,
    same "no project needs its own copy" principle as this module itself —
    no Dockerfile step needed. See .abi/specs/agent-custom-elements.md.
    """
    try:
        src_dir = importlib.resources.files("abi_core.ui") / "elements"
        dest_dir = Path("public/elements")
        dest_dir.mkdir(parents=True, exist_ok=True)

        for jsx_file in src_dir.iterdir():
            if jsx_file.name.endswith(".jsx"):
                dest = dest_dir / jsx_file.name
                src_bytes = jsx_file.read_bytes()
                if not dest.exists() or dest.read_bytes() != src_bytes:
                    dest.write_bytes(src_bytes)
    except Exception as e:
        # Non-fatal: custom elements just won't render (the built-in ones
        # from .abi/specs/agent-rich-elements.md are unaffected). Common
        # cause: a read-only container filesystem — see "Puntos débiles"
        # in .abi/specs/agent-custom-elements.md.
        from abi_core.common.utils import abi_logging

        abi_logging(f"[⚠️] Could not install bundled custom elements: {e}", level="warning")


_install_bundled_elements()


def _install_ws_connect_tracer() -> None:
    """TEMPORARY diagnostic — remove once the session-churn root cause is
    confirmed (investigation started 2026-09-26).

    Logs the browser's own Socket.IO ``sessionId`` on every WS ``connect``.
    Chainlit's own ``restore_existing_session()`` (chainlit/socket.py) keeps
    ``cl.user_session`` (and our cached AgentStreamClient token) alive across
    a reconnect ONLY if the client resends the SAME ``sessionId`` — if it
    doesn't, every reconnect falls back to the slow Postgres thread-resume
    path (on_chat_resume) instead of the free in-memory one, which would
    explain sessions churning every few minutes during otherwise-continuous,
    active use — reproduced live 2026-09-26, unexplained by TTL expiry or
    container restarts. Wraps (doesn't replace) chainlit.socket's own
    "connect" handler by re-registering on the same `sio` instance —
    verified safe: python-socketio's `.on()` is a plain dict assignment
    (`self.handlers[namespace][event] = handler`), so this overwrites
    cleanly with no duplicate-handler conflict.
    """
    try:
        import chainlit.socket as cl_socket

        original_connect = cl_socket.connect

        async def _traced_connect(sid, environ, auth):
            from abi_core.common.utils import abi_logging

            abi_logging(
                f"[🔌] WS connect: sid={sid} sessionId={auth.get('sessionId')} "
                f"threadId={auth.get('threadId')} clientType={auth.get('clientType')}",
                level="info",
            )
            return await original_connect(sid, environ, auth)

        cl_socket.sio.on("connect")(_traced_connect)
    except Exception as e:
        from abi_core.common.utils import abi_logging

        abi_logging(f"[⚠️] Could not install WS connect tracer: {e}", level="warning")


_install_ws_connect_tracer()

AGENT_URL = os.getenv("ABI_AGENT_URL", "http://localhost:8083")
UI_TITLE = os.getenv("ABI_UI_TITLE", "ABI")

# Sentinel queries the orchestrator's classify_query step (and
# abi_core.agent.plan_confirmation) recognize as a plan-confirmation reply.
_PLAN_CONFIRM_SENTINELS = {
    "approve": "__plan_confirm_approve__",
    "reject": "__plan_confirm_reject__",
    "modify": "__plan_confirm_modify__",
}


def _build_element(payload: dict) -> "cl.Element | None":
    """Build a Chainlit element from an ``AgentResponse.element(...)``
    payload (``{"element_type": ..., "name": ..., "props": {...}}``).

    See .abi/specs/agent-rich-elements.md.
    """
    element_type = payload.get("element_type")
    props = payload.get("props") or {}
    name = payload.get("name") or element_type

    if element_type == "qr":
        from abi_core.common.qr_code import generate_qr_png

        return cl.Image(name=name, content=generate_qr_png(props.get("data", "")))

    if element_type in ("image", "file", "pdf", "audio", "video", "text"):
        # Element.from_dict already knows how to build these from
        # url/path/content — no need to re-implement the mapping per type.
        return cl.Element.from_dict({"type": element_type, "name": name, **props})

    if element_type == "dataframe":
        import pandas as pd

        return cl.Dataframe(name=name, data=pd.DataFrame(**props))

    # plotly/pyplot/tasklist are out of scope — see .abi/specs/agent-rich-elements.md
    # ("Puntos débiles"). Anything else is assumed to be the name of a
    # custom .jsx element (bundled via _install_bundled_elements(), or
    # provided by the project's own public/elements/) — Chainlit resolves
    # it by name; no whitelist needed here. See
    # .abi/specs/agent-custom-elements.md.
    if element_type in ("plotly", "pyplot", "tasklist"):
        from abi_core.common.utils import abi_logging

        abi_logging(f"[⚠️] Unsupported element_type '{element_type}', skipping", level="warning")
        return None

    return cl.CustomElement(name=element_type, props=props)


# Background tasks (admin error notifications) must be kept referenced or
# asyncio may garbage-collect them mid-flight — same pattern as
# orchestrator/agent/steps.py's _spawn_background. See
# .abi/specs/chainlit-error-boundary-admin-notify.md
_background_tasks: set = set()


def _spawn_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _notify_admin_of_error(error_detail: str, context_id: str | None) -> None:
    """Best-effort email to the admin with the real error — never raises,
    never blocks the caller. Independent of the OAuth conditional import
    (abi_core.ui.auth's _notify_admin_of_waiting_list) so error reporting
    works whether or not OAuth is configured. Runs the blocking smtplib
    call in a thread so it never stalls the message render.
    """
    from abi_core.common.utils import abi_logging

    host = os.getenv("SMTP_HOST")
    admin_email = os.getenv("ADMIN_NOTIFICATION_EMAIL")
    if not host or not admin_email:
        abi_logging(
            "[⚠️] SMTP_HOST/ADMIN_NOTIFICATION_EMAIL not set — skipping error "
            f"notification (context={context_id})",
            level="warning",
        )
        return

    def _send() -> None:
        msg = EmailMessage()
        msg["Subject"] = "ABI Swarm — system error"
        msg["From"] = os.getenv("SMTP_FROM", admin_email)
        msg["To"] = admin_email
        msg.set_content(
            f"Context: {context_id}\n\n{error_detail}"
        )
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASSWORD")
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)

    try:
        await asyncio.to_thread(_send)
    except Exception as e:  # noqa: BLE001 — never let a notification failure surface
        abi_logging(f"[⚠️] Could not send error notification email: {e}", level="warning")


def _get_client() -> AgentStreamClient:
    """One AgentStreamClient per chat — its session token persists across
    every message in this chat (cl.user_session is per-connection, so
    storing the live instance there needs no serialization)."""
    client = cl.user_session.get("abi_stream_client")

    # TEMPORARY diagnostic (paired with _install_ws_connect_tracer, remove
    # together once the session-churn root cause is confirmed) — logs
    # whether cl.user_session actually still had a cached client with a
    # live token, or is starting from scratch, on every call site
    # (on_message AND action_callback both call this).
    from abi_core.common.utils import abi_logging

    if client is None:
        abi_logging("[🔍] _get_client: no cached client in cl.user_session — creating new", level="info")
    else:
        abi_logging(
            f"[🔍] _get_client: reusing cached client, token={'set' if client._token else 'None'}",
            level="info",
        )

    if client is None:
        client = AgentStreamClient(AGENT_URL)
        cl.user_session.set("abi_stream_client", client)
    return client


async def _sync_session_token_to_thread() -> None:
    """Persist the current session token into this thread's metadata.

    The missing write-side of the bridge from
    .abi/specs/implemented/chainlit-oauth-login-session-continuity.md
    (section 3): on_chat_resume (abi_core.ui.auth) already reads
    thread.metadata["abi_session_token"] back to rebuild the
    AgentStreamClient on reconnect — but nothing ever wrote that key, so
    every resume got token=None and silently started a brand-new backend
    session, losing all conversation context. Called after ensure_session()
    (on_chat_start) and again at the end of every _stream_to_agent() call,
    since a token can also be refreshed mid-conversation (see
    AgentStreamClient.stream()'s X-Session-Resolved retry path).

    Best-effort, same convention as this module's other memory/session
    calls: no data layer configured (no DATABASE_URL), no thread yet, or no
    token all no-op silently instead of raising.
    """
    token = _get_client()._token
    if not token or cl.user_session.get("abi_session_token_saved") == token:
        return
    try:
        from chainlit.data import get_data_layer

        data_layer = get_data_layer()
        thread_id = cl.context.session.thread_id
        if data_layer and thread_id:
            await data_layer.update_thread(thread_id, metadata={"abi_session_token": token})
            cl.user_session.set("abi_session_token_saved", token)
    except Exception as e:
        from abi_core.common.utils import abi_logging

        abi_logging(f"[⚠️] Could not persist session token to thread: {e}", level="warning")


def _build_identity_chain() -> "list[dict] | None":
    """Build the chatui->orchestrator identity chain — see
    .abi/specs/not-implemented/identity-chain-hmac-contract.md.

    Cheap to call on every message (local HMAC only, no network round-trip,
    unlike the opaque token). Returns None — callers then fall back to the
    existing Bearer-token flow, unchanged — when there's no authenticated
    user (no OAuth configured, or not logged in) or no hop secret
    configured, since the chain has nothing meaningful to prove in either
    case.
    """
    secret = os.getenv("HOP_SECRET_CHATUI_ORCHESTRATOR")
    if not secret:
        return None
    user = getattr(cl.context.session, "user", None)
    user_id = getattr(user, "id", None) if user else None
    thread_id = getattr(cl.context.session, "thread_id", None)
    if not user_id or not thread_id:
        return None

    from abi_core.security.identity_chain import build_chain

    return build_chain(secret, [("user_id", user_id), ("thread_id", thread_id)])


@cl.on_chat_start
async def on_start():
    await _get_client().ensure_session()
    await _sync_session_token_to_thread()
    await cl.Message(content=f"🐝 **{UI_TITLE}** ready. What do you want to build?").send()


async def _stream_to_agent(query: str) -> None:
    """Send `query` to the agent and render the response.

    Shared by on_message (free-text turns) and the plan-confirmation action
    callback (button clicks) — both are just a query string to the agent, the
    server doesn't distinguish "action" from "text" (see web_interface.py's
    /stream contract).
    """
    # Parent step for the whole run; a child step opens per plan task
    # (meta.task_key) once execution reaches it, so each task stays visible
    # in the chat instead of being overwritten by the next one — see
    # .abi/specs/chainlit-per-step-ui.md. Heartbeats with no task_key yet
    # (routing/planning, before any task starts) update the parent.
    processing_step = cl.Step(name="Processing", type="run")
    await processing_step.send()

    current_task_key = None
    task_step = None

    final_content = ""
    actions_sent = False
    collected_elements = []

    async for parsed in _get_client().stream(query, identity_chain=_build_identity_chain()):
        response_type = parsed.get("response_type", "")
        content = parsed.get("content", "")

        if response_type == "status" and content:
            meta = parsed.get("meta", {}) or {}
            task_key = meta.get("task_key")
            agent = meta.get("agent")

            if task_key and task_key != current_task_key:
                current_task_key = task_key
                task_step = cl.Step(
                    name=meta.get("task_label") or task_key,
                    type="run",
                    parent_id=processing_step.id,
                )
                await task_step.send()
            elif not task_key and agent:
                # No plan task running yet (routing/planning/synthesis) —
                # the parent step is the only one visible, so it should
                # show who's actually working, not a static "Processing".
                # Was lost when the single-step design became parent+child
                # steps — see .abi/specs/chainlit-active-agent-label.md.
                processing_step.name = agent

            target_step = task_step or processing_step
            target_step.output = content
            await target_step.update()
        elif response_type == "element" and content:
            element = _build_element(content)
            if element is not None:
                collected_elements.append(element)
        elif response_type == "text" and content:
            final_content = content
        elif response_type == "data" and content:
            # Final result payload (AgentResponse.result). Render something
            # human-readable: pull "result" if present, otherwise stringify
            # the payload.
            if isinstance(content, dict):
                final_content = str(content.get("result", content))
            else:
                final_content = str(content)
        elif response_type == "input_required" and content:
            meta = parsed.get("meta", {}) or {}
            if meta.get("action_type") == "plan_confirmation":
                actions = [
                    cl.Action(name="plan_confirm", payload={"choice": "approve"}, label="✅ Aprobar"),
                    cl.Action(name="plan_confirm", payload={"choice": "reject"}, label="❌ Rechazar"),
                    cl.Action(name="plan_confirm", payload={"choice": "modify"}, label="✏️ Modificar"),
                ]
                await cl.Message(content=content, actions=actions).send()
                # Kept so on_plan_confirm can remove() them once any one is
                # clicked — otherwise all three stay active/clickable after
                # the user already chose one (double-submit risk).
                cl.user_session.set("pending_plan_actions", actions)
                actions_sent = True
            elif meta.get("questions"):
                # Structured clarification questions (see
                # .abi/specs/deterministic-clarification-answers.md) — render
                # a real form instead of asking the user to type "q1: ...".
                # Submitting it sends a deterministic sentinel the backend
                # recognizes without an LLM call (same reasoning as the
                # plan-confirmation buttons above).
                final_content = content
                collected_elements.append(cl.CustomElement(
                    name="ClarificationForm",
                    props={"questions": meta["questions"], "answers": {}},
                ))
            else:
                # The agent needs clarification (or plain input); surface as
                # text. The next message continues the same session (same
                # token).
                final_content = content
        elif response_type == "error" and content:
            _spawn_background(_notify_admin_of_error(content, _get_client()._token))
            final_content = "❌ The system is currently unavailable. Please try again later."

    if task_step is not None:
        await task_step.update()
    processing_step.output = "Done"
    await processing_step.update()

    if not actions_sent:
        # Created only now, with real content already in hand — previously
        # this was a cl.Message(content="") sent empty at the very top of
        # the function, which rendered as a second, blank ABI-avatar bubble
        # sitting above the "Usado {agent}" progress step for the entire
        # duration of the turn (reported live 2026-09-25).
        response_msg = cl.Message(content=final_content or "No response received.")
        response_msg.elements = collected_elements
        await response_msg.send()

    await _sync_session_token_to_thread()


@cl.on_message
async def on_message(message: cl.Message):
    """Send the user message to the agent and stream the response."""
    await _stream_to_agent(message.content)


@cl.action_callback("plan_confirm")
async def on_plan_confirm(action: cl.Action):
    """Handle a plan-confirmation button click (approve/reject/modify)."""
    # Remove all three buttons the instant one is clicked — otherwise they
    # stay active/clickable (double-submit risk) while the choice is
    # already being processed.
    pending_actions = cl.user_session.get("pending_plan_actions") or []
    for a in pending_actions:
        try:
            await a.remove()
        except Exception:
            pass
    cl.user_session.set("pending_plan_actions", None)

    choice = action.payload.get("choice")
    await _stream_to_agent(_PLAN_CONFIRM_SENTINELS.get(choice, _PLAN_CONFIRM_SENTINELS["reject"]))


@cl.action_callback("clarification_answer")
async def on_clarification_answer(action: cl.Action):
    """Handle a ClarificationForm submission.

    Mirrors on_plan_confirm above: the form (ClarificationForm.jsx) calls
    callAction instead of sendUserMessage specifically so the raw
    {"_sentinel": ..., "answers": {...}} payload never renders as a visible
    chat bubble — callAction delivers it straight here, with no user-message
    echo at all. The backend (orchestrator steps.py::classify_query) still
    expects the exact same JSON sentinel string it always has; only the
    transport changed.
    """
    answers = action.payload.get("answers", {})
    await _stream_to_agent(json.dumps({
        "_sentinel": "__clarification_answer__",
        "answers": answers,
    }))
