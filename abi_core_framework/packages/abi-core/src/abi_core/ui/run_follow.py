"""Keep a run's progress live when the user comes back to its conversation.

The run itself keeps going after its websocket disconnects (Chainlit only
cancels it on an explicit stop), but its updates go to the old socket. A
resumed session follows the run through Chainlit's database instead: the
run step's metadata carries an ``abi_run`` marker with a heartbeat, and a
watcher bound to the resumed session reads it back and relays it to the
page. Works across chatui replicas, since the state lives in the database,
not in the process that runs the task. See
.abi/specs/not-implemented/ux/chainlit-run-progress-resume.md.

The decision logic is plain functions (no Chainlit import) so it can be
tested on its own; only ``follow_run`` and its helpers touch Chainlit.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from abi_core.ui.run_progress import format_duration, ui_language

# Seconds without a heartbeat after which a "running" run is considered dead
# (e.g. chatui restarted mid-run).
STALE_AFTER_SECONDS = 30
# The run persists its heartbeat this often (the screen still ticks every 1s).
HEARTBEAT_SECONDS = 5
# How often the resumed page refreshes the run step / the whole conversation.
FOLLOW_STEP_SECONDS = 1
FOLLOW_THREAD_SECONDS = 5

STOP_KEY = "abi_stop_requested"
# user_session keys of a resumed session.
FOLLOWER_KEY = "abi_run_follower"
FOLLOWED_RUN_KEY = "abi_followed_run"

_INTERRUPTED = {"es": "Interrumpido", "en": "Interrupted"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _metadata(step: dict) -> dict:
    raw = step.get("metadata") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def run_marker(step: dict) -> dict:
    """The ``abi_run`` marker of a step, or {} if it isn't a run step."""
    marker = _metadata(step).get("abi_run")
    return marker if isinstance(marker, dict) else {}


def find_active_run(steps: list, now: datetime) -> tuple[Optional[dict], Optional[str]]:
    """The run step still marked running in this conversation, and whether
    to ``"follow"`` it (fresh heartbeat) or treat it as ``"interrupted"``.
    ``(None, None)`` when nothing is running."""
    for step in reversed(steps or []):
        marker = run_marker(step)
        if marker.get("state") != "running" or step.get("end"):
            continue
        beat = _parse_iso(marker.get("heartbeat_at"))
        if beat is None or (now - beat).total_seconds() > STALE_AFTER_SECONDS:
            return step, "interrupted"
        return step, "follow"
    return None, None


def is_still_running(step: dict, now: datetime) -> bool:
    marker = run_marker(step)
    if marker.get("state") != "running" or step.get("end"):
        return False
    beat = _parse_iso(marker.get("heartbeat_at"))
    return beat is not None and (now - beat).total_seconds() <= STALE_AFTER_SECONDS


def running_name(step: dict, now: datetime) -> str:
    """Header for a resumed page: the run's label plus the elapsed time
    computed from ``start`` — so the counter keeps moving every second even
    though the database only gets a heartbeat every few seconds."""
    label = run_marker(step).get("label")
    start = _parse_iso(step.get("start"))
    if not label or start is None:
        return step.get("name") or ""
    return f"{label} · {format_duration(max(0.0, (now - start).total_seconds()))}"


def interrupted_name(step: dict, lang: Optional[str], now: datetime) -> str:
    word = _INTERRUPTED[ui_language(lang)]
    start = _parse_iso(step.get("start"))
    if start is None:
        return word
    return f"{word} · {format_duration(max(0.0, (now - start).total_seconds()))}"


def _fingerprint(item: dict) -> str:
    return json.dumps(item, sort_keys=True, default=str)


def diff_items(known: dict, items: list) -> tuple[list, list, dict]:
    """Compare a fresh list of steps/elements with what the page already
    has (``known``: id → fingerprint). Returns (new, changed, updated known)."""
    new, changed = [], []
    known = dict(known)
    for item in items or []:
        item_id = item.get("id")
        if not item_id:
            continue
        fp = _fingerprint(item)
        if item_id not in known:
            new.append(item)
        elif known[item_id] != fp:
            changed.append(item)
        known[item_id] = fp
    return new, changed, known


def stop_requested(thread_metadata, run_step_id: str) -> bool:
    if isinstance(thread_metadata, str):
        try:
            thread_metadata = json.loads(thread_metadata)
        except json.JSONDecodeError:
            return False
    return isinstance(thread_metadata, dict) and thread_metadata.get(STOP_KEY) == run_step_id


# ── Chainlit side ───────────────────────────────────────────────────────


def _data_layer():
    from chainlit.data import get_data_layer

    return get_data_layer()


async def read_stop_request(thread_id: Optional[str], run_step_id: str) -> bool:
    """Whether a resumed page asked to stop this run (one indexed read)."""
    data_layer = _data_layer()
    if not data_layer or not thread_id or not hasattr(data_layer, "execute_sql"):
        return False
    rows = await data_layer.execute_sql(
        query='SELECT "metadata" FROM threads WHERE "id" = :id', parameters={"id": thread_id}
    )
    if not isinstance(rows, list) or not rows:
        return False
    return stop_requested(rows[0].get("metadata"), run_step_id)


async def request_stop(thread_id: str, run_step_id: str) -> None:
    """Ask the run (wherever it runs) to stop. Thread metadata, not the
    step's: the run rewrites its own step metadata on every heartbeat, while
    update_thread merges into what is already stored."""
    data_layer = _data_layer()
    if data_layer and thread_id:
        await data_layer.update_thread(thread_id, metadata={STOP_KEY: run_step_id})


def start_following(thread: dict) -> None:
    """Called from on_chat_resume: if this conversation has a run still
    marked running, follow it from this session (or close it as
    interrupted if its heartbeat is stale)."""
    import chainlit as cl

    run_step, mode = find_active_run(thread.get("steps"), datetime.now(timezone.utc))
    if run_step is None:
        return
    lang = getattr(cl.context.session, "language", None)
    task = asyncio.create_task(follow_run(thread, run_step, mode, lang))
    cl.user_session.set(FOLLOWER_KEY, task)
    if mode == "follow":
        cl.user_session.set(FOLLOWED_RUN_KEY, run_step["id"])


async def follow_run(thread: dict, run_step: dict, mode: str, lang: Optional[str]) -> None:
    """Watcher for a resumed session. Runs until the run ends, goes stale,
    or the task is cancelled (the user leaves this conversation again)."""
    import chainlit as cl

    data_layer = _data_layer()
    if not data_layer:
        return
    emitter = cl.context.emitter
    thread_id = thread.get("id")
    run_id = run_step["id"]

    # on_chat_resume runs before Chainlit sends the thread to the page, and
    # the page gets a task_end on connect: wait one tick so what follows
    # lands on a page that already has the steps.
    await asyncio.sleep(FOLLOW_STEP_SECONDS)

    if mode == "interrupted":
        await _mark_interrupted(data_layer, emitter, run_step, lang)
        return

    _, _, known_steps = diff_items({}, thread.get("steps"))
    _, _, known_elements = diff_items({}, thread.get("elements"))

    async def sync_thread() -> None:
        nonlocal known_steps, known_elements
        fresh = await data_layer.get_thread(thread_id)
        if not fresh:
            return
        new, changed, known_steps = diff_items(known_steps, fresh.get("steps"))
        for step in new:
            if step.get("id") != run_id:
                await emitter.send_step(step)
        for step in changed:
            if step.get("id") != run_id:
                await emitter.update_step(step)
        new_el, _, known_elements = diff_items(known_elements, fresh.get("elements"))
        for element in new_el:
            await emitter.send_element(element)

    await emitter.task_start()
    elapsed = 0
    try:
        while True:
            step = await data_layer.get_step(run_id)
            now = datetime.now(timezone.utc)
            if step is None:
                return
            if is_still_running(step, now):
                await emitter.update_step({**step, "name": running_name(step, now)})
            else:
                if run_marker(step).get("state") == "running" and not step.get("end"):
                    await _mark_interrupted(data_layer, emitter, step, lang)
                else:
                    await emitter.update_step(step)
                await sync_thread()
                return
            if elapsed % FOLLOW_THREAD_SECONDS == 0:
                await sync_thread()
            await asyncio.sleep(FOLLOW_STEP_SECONDS)
            elapsed += FOLLOW_STEP_SECONDS
    finally:
        try:
            await emitter.task_end()
        except Exception:
            pass


async def _mark_interrupted(data_layer, emitter, step: dict, lang: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    metadata = {**_metadata(step), "avatarName": "abi_idle",
                "abi_run": {**run_marker(step), "state": "interrupted"}}
    metadata["abi_run"].pop("heartbeat_at", None)
    updated = {
        **step,
        "name": interrupted_name(step, lang, now),
        "end": now.isoformat(),
        "isError": True,
        "metadata": metadata,
    }
    await data_layer.update_step(updated)
    await emitter.update_step(updated)
