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

import importlib.resources
import os
import shutil
import warnings
from pathlib import Path

import chainlit as cl

from abi_core.client.agent_stream_client import AgentStreamClient

# Suppress httpcore async generator cleanup warnings (cosmetic, non-blocking)
warnings.filterwarnings("ignore", message=".*async generator ignored GeneratorExit.*")


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


def _get_client() -> AgentStreamClient:
    """One AgentStreamClient per chat — its session token persists across
    every message in this chat (cl.user_session is per-connection, so
    storing the live instance there needs no serialization)."""
    client = cl.user_session.get("abi_stream_client")
    if client is None:
        client = AgentStreamClient(AGENT_URL)
        cl.user_session.set("abi_stream_client", client)
    return client


@cl.on_chat_start
async def on_start():
    await _get_client().ensure_session()
    await cl.Message(content=f"🐝 **{UI_TITLE}** ready. What do you want to build?").send()


async def _stream_to_agent(query: str) -> None:
    """Send `query` to the agent and render the response.

    Shared by on_message (free-text turns) and the plan-confirmation action
    callback (button clicks) — both are just a query string to the agent, the
    server doesn't distinguish "action" from "text" (see web_interface.py's
    /stream contract).
    """
    response_msg = cl.Message(content="")
    await response_msg.send()

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

    async for parsed in _get_client().stream(query):
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
            final_content = f"❌ {content}"

    if task_step is not None:
        await task_step.update()
    processing_step.output = "Done"
    await processing_step.update()

    if actions_sent:
        try:
            await response_msg.remove()
        except Exception:
            pass
    else:
        response_msg.content = final_content or "No response received."
        response_msg.elements = collected_elements
        await response_msg.update()


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
