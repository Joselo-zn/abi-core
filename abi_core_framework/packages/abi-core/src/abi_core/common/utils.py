import logging
import os 
import sys
import json
import threading
from datetime import datetime, timezone

from typing import Any, Optional
from abi_core.common.types import ServerConfig

# ── ABI Logging Configuration ──────────────────────────────────
#
# Dual-backend: stdout (always) + MinIO buffer (opt-in).
# Enable MinIO backend with LOG_TO_ARTIFACT_STORE=true.
# Logs accumulate in memory and flush to MinIO on demand via flush_logs().
#
# Env vars:
#   LOG_TO_ARTIFACT_STORE  — true/false (default: false)
#   LOG_AGENT_NAME         — agent identifier for log key (default: from AGENT_NAME or "unknown")
#   LOG_BUCKET             — MinIO bucket for logs (default: "abi-logs")
#   ARTIFACT_ENDPOINT      — MinIO endpoint (reused from ArtifactStore)
#   ARTIFACT_ACCESS_KEY    — MinIO access key
#   ARTIFACT_SECRET_KEY    — MinIO secret key

_abi_logger = None
_log_buffer = []
_log_buffer_lock = threading.Lock()
_log_to_store = os.getenv("LOG_TO_ARTIFACT_STORE", "false").lower() in ("true", "1", "yes")
_log_agent_name = os.getenv("LOG_AGENT_NAME", "") or os.getenv("AGENT_NAME", "unknown")
_log_bucket = os.getenv("LOG_BUCKET", "abi-logs")


class _MinIOBufferHandler(logging.Handler):
    """Logging handler that accumulates formatted lines in a memory buffer."""

    def emit(self, record):
        try:
            line = self.format(record)
            with _log_buffer_lock:
                _log_buffer.append(line)
        except Exception:
            pass  # never break logging


def _setup_abi_logger():
    """Setup ABI logger with stdout + optional MinIO buffer handler."""
    global _abi_logger
    
    if _abi_logger is not None:
        return _abi_logger
    
    debug_enabled = os.getenv('ABI_SETTINGS_LOGGING_DEBUG', 'False').lower() in ('true', '1', 'yes', 'on')
    
    _abi_logger = logging.getLogger('abi_logger')
    _abi_logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    _abi_logger.handlers.clear()
    
    formatter = logging.Formatter(
        '%(asctime)s - ABI - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler 1: stdout (always)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    stdout_handler.setFormatter(formatter)
    _abi_logger.addHandler(stdout_handler)
    
    # Handler 2: MinIO buffer (opt-in)
    if _log_to_store:
        buffer_handler = _MinIOBufferHandler()
        buffer_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        buffer_handler.setFormatter(formatter)
        _abi_logger.addHandler(buffer_handler)
    
    _abi_logger.propagate = False
    return _abi_logger


def abi_logging(message: str, level: str = 'info'):
    """ABI centralized logging — stdout + optional MinIO buffer.
    
    Args:
        message: The message to log.
        level: Log level ('debug', 'info', 'warning', 'error', 'critical').
    """
    logger = _setup_abi_logger()
    
    level = level.lower()
    log_fn = {
        'debug': logger.debug,
        'info': logger.info,
        'warning': logger.warning,
        'error': logger.error,
        'critical': logger.critical,
    }.get(level, logger.info)
    log_fn(message)


async def flush_logs(agent_name: str = None, bucket: str = None, task_id: str = None):
    """Flush buffered logs to MinIO.
    
    Call this before destroying ephemeral containers or at end of tasks.
    No-op if LOG_TO_ARTIFACT_STORE is not enabled or buffer is empty.
    
    Args:
        agent_name: Override agent name for the log key (default: from env).
        bucket: Override bucket name (default: from env).
        task_id: Task/execution ID to group logs across agents.
                 Structure: logs/{task_id}/{agent_name}.log
    """
    if not _log_to_store:
        return
    
    with _log_buffer_lock:
        if not _log_buffer:
            return
        lines = list(_log_buffer)
        _log_buffer.clear()
    
    name = agent_name or _log_agent_name
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    # Group by task_id if available, otherwise by agent name
    if task_id:
        key = f"user-task-{task_id}/{name}.log"
    else:
        key = f"logs/{name}/{ts}.log"
    
    content = "\n".join(lines).encode("utf-8")
    
    try:
        from abi_core.common.artifact_store import ArtifactStore
        store = ArtifactStore(bucket=bucket or _log_bucket)
        await store.ensure_bucket()
        await store.upload(key, content, metadata={"agent": name, "type": "log", "task_id": task_id or ""})
        # Use print here to avoid recursion (abi_logging → handler → buffer → ...)
        print(f"[📋] Flushed {len(lines)} log lines to {key}", flush=True)
    except Exception as e:
        print(f"[⚠️] Failed to flush logs to MinIO: {e}", flush=True)


def get_log_buffer_size() -> int:
    """Return current number of buffered log lines."""
    with _log_buffer_lock:
        return len(_log_buffer)

import re
from typing import Mapping

_DEFAULT_SEMANTIC_LAYER = 'http://abi-semantic-layer:10100'
_DEFAULT_MCP_TRANSPORT = 'streamable-http'


def _semantic_layer_endpoint(environ: Mapping[str, str]):
    """(url, host, port, transport, scheme) from SEMANTIC_LAYER_HOST,
    SEMANTIC_LAYER_PORT and MCP_TRANSPORT. SEMANTIC_LAYER_HOST may be a full
    URL (http://host:port, or https://host on a managed endpoint such as Cloud
    Run, where no port means 443) or a bare hostname (then SEMANTIC_LAYER_PORT,
    default 10100, over http)."""
    url = environ.get('SEMANTIC_LAYER_HOST', _DEFAULT_SEMANTIC_LAYER)
    transport = environ.get('MCP_TRANSPORT', _DEFAULT_MCP_TRANSPORT)
    url_match = re.match(r'(https?)://([^:/]+)(?::(\d+))?', url)
    if url_match:
        scheme = url_match.group(1)
        host = url_match.group(2)
        if url_match.group(3):
            port = int(url_match.group(3))
        else:
            port = 443 if scheme == 'https' else 10100
    else:
        scheme = 'http'
        host = url.split(':')[0]
        port = int(environ.get('SEMANTIC_LAYER_PORT', 10100))
        url = f'http://{host}:{port}'
    return url, host, port, transport, scheme


# Compatibility aliases, read once at import. Nothing in abi-core uses them;
# get_mcp_server_config() reads the environment on every call instead.
SEMANTIC_LAYER_URL = os.getenv('SEMANTIC_LAYER_HOST', _DEFAULT_SEMANTIC_LAYER)
URL, HOST, PORT, MCP_TRANSPORT, _ = _semantic_layer_endpoint(os.environ)


def get_mcp_server_config(environ: Optional[Mapping[str, str]] = None) -> ServerConfig:
    """Get the MCP server configuration, read from the environment on every
    call (or from `environ` when given).

    SEMANTIC_LAYER_HOST can be:
    - Full URL: http://hostname:port
    - Hostname only: hostname (uses SEMANTIC_LAYER_PORT or default 10100)

    MCP_TRANSPORT:
    - 'streamable-http' (default)
    - 'sse' (deprecated by MCP in favour of streamable-http)

    Returns:
        ServerConfig with parsed host, port, transport, and url
    """
    url, host, port, transport, scheme = _semantic_layer_endpoint(os.environ if environ is None else environ)
    abi_logging(f'[*] MCP Config: Host={host}, Port={port}, Transport={transport}, Scheme={scheme}', level='debug')
    return ServerConfig(
        host=host,
        port=port,
        transport=transport,
        url=url,
        scheme=scheme,
    )

def truncate(obj: Any, max_chars: int = 4000) -> str:
    """Convierte a JSON y recorta para no exceder num_ctx."""
    text = json.dumps(obj, ensure_ascii=False)
    return text if len(text) <= max_chars else text[:max_chars] + "…"


# ── LLM response helpers ───────────────────────────────────────

def clean_llm_json(raw: str) -> dict:
    """Clean and parse a JSON response from an LLM.

    Handles common LLM quirks:
    - Markdown code fences (```json ... ```)
    - Double braces {{ }} from template confusion
    - Leading/trailing text around JSON
    - Multiple JSON blocks (takes the first valid one)

    Returns parsed dict on success, or a fallback single-task plan
    on parse failure.
    """
    import re

    cleaned = raw.strip()

    # Strip markdown code fences
    if cleaned.startswith('```json'):
        cleaned = cleaned[7:]
    if cleaned.startswith('```'):
        cleaned = cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Fix double braces from LLM hallucination
    cleaned = cleaned.replace('{{', '{').replace('}}', '}')

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract JSON from surrounding text — find first { to last matching }
    json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)
    for block in json_blocks:
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict) and ("status" in parsed or "plan" in parsed):
                return parsed
        except json.JSONDecodeError:
            continue

    # Last resort: find the outermost { ... } pair
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    abi_logging("[⚠️] Failed to parse LLM JSON, returning fallback", level="warning")
    return {
        "status": "ready",
        "plan": {
            "objective": "Complete user request",
            "tasks": [{
                "task_id": "task_1",
                "description": _clean_description(raw),
                "dependencies": [],
            }],
            "execution_strategy": "sequential",
        },
    }


def _clean_description(text: str) -> str:
    """Strip markdown formatting and code blocks from a task description.

    Used to sanitize LLM output that leaks markdown into structured fields.
    """
    import re

    # Remove code blocks (```...```)
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    # Remove markdown headers (### Header)
    cleaned = re.sub(r'^#{1,6}\s+.*$', '', cleaned, flags=re.MULTILINE)
    # Remove bold/italic markers
    cleaned = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', cleaned)
    # Collapse multiple newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    # Truncate if too long (descriptions should be concise)
    if len(cleaned) > 500:
        cleaned = cleaned[:500] + "..."
    return cleaned


def format_plan_summary(plan: dict, model_status: dict = None) -> str:
    """Format a plan dict into a human-readable markdown summary.

    Args:
        plan: Dict with ``objective``, ``tasks``, ``execution_strategy``,
            and optionally ``methodology``/``methodology_rationale``.
        model_status: Optional {task_id: {"model": ..., "location": str|None}}
            from the orchestrator's check_model_availability tool — shown per
            task when present.

    Returns:
        Formatted string.
    """
    objective = plan.get("objective", "Complete user request")
    tasks = plan.get("tasks", [])
    strategy = plan.get("execution_strategy", "sequential")
    model_status = model_status or {}

    lines = [
        "📋 **Plan Created**\n",
        f"🎯 **Objective:** {objective}\n",
    ]

    lines.append(f"📊 **Strategy:** {strategy.capitalize()}\n")
    lines.append(f"**Tasks ({len(tasks)}):**\n")

    for i, t in enumerate(tasks, 1):
        tid = t.get("task_id", f"task_{i}")
        desc = t.get("description", "")
        agents = t.get("agents", [])
        deps = t.get("dependencies", [])

        lines.append(f"\n{i}. **{tid}:** {desc}")
        if agents and agents[0]:
            names = [a.get("name", "Unknown") for a in agents if a]
            lines.append(f"   👤 Agent(s): {', '.join(names)}")
        else:
            lines.append("   🆕 A new agent will be created")
        if deps:
            lines.append(f"   🔗 Depends on: {', '.join(deps)}")

        ms = model_status.get(tid)
        if ms:
            if ms.get("location"):
                lines.append(f"   ✅ Model: {ms['model']}")
            else:
                lines.append(f"   ⬇️ Model: {ms['model']} (will be downloaded)")

    lines.append("\n**Reply to approve, reject, or request changes.**")
    return "\n".join(lines)


def plan_execution_order(tasks: list) -> list:
    """Stable topological sort — the order a plan's tasks actually run in:
    every task after the tasks it depends on, plan order kept among tasks
    that are ready at the same time.

    Dependencies pointing outside `tasks` (e.g. a retry's reduced plan,
    whose already-built siblings aren't in this list) are ignored. A cycle
    can't be ordered — remaining tasks are appended in plan order and
    logged. Shared by the orchestrator's build_workflow and the plan review
    card, so both number tasks the same way.
    """
    ids = {t.get("task_id") for t in tasks}
    pending = list(tasks)
    placed: set = set()
    ordered = []
    while pending:
        ready = [
            t for t in pending
            if all(d in placed or d not in ids for d in t.get("dependencies", []))
        ]
        if not ready:
            abi_logging(
                f"[⚠️] Dependency cycle among {[t.get('task_id') for t in pending]} "
                "— keeping plan order for them",
                level="warning",
            )
            ordered.extend(pending)
            break
        for t in ready:
            ordered.append(t)
            placed.add(t.get("task_id"))
            pending.remove(t)
    return ordered


def _fallback_task_title(task: dict) -> str:
    """Title for a task the Planner gave none: the description with its
    "Write a <language> file named <file> that" lead-in removed, cut to
    its first sentence — or the target filename / task id."""
    import re

    desc = " ".join(str(task.get("description", "")).split())
    desc = re.sub(
        r"^(?:write|create)\s+an?\s+(?:[\w+#.-]+\s+)?(?:file|script)\s+named\s+\S+\s*"
        r"(?:that|which|to|with|containing)?\s*",
        "", desc, flags=re.IGNORECASE,
    )
    desc = desc.split(". ")[0].strip(" .")
    if desc:
        desc = desc[0].upper() + desc[1:]
        return desc if len(desc) <= 60 else desc[:59].rstrip() + "…"
    target = task.get("target") or {}
    return target.get("tag") or str(task.get("task_id", ""))


def build_plan_view(plan: dict, model_status: Optional[dict] = None) -> dict:
    """Presentation data for reviewing *plan* before approval — what the
    Chainlit PlanReview card renders. Deterministic, no LLM.

    Steps come in execution order (``plan_execution_order``), numbered
    1..n — the same numbering the run progress uses. ``notices`` hold only
    things the user should actually know (a model that will be
    downloaded), as codes the UI localizes. Methodology, strategy and
    infrastructure URLs are left out on purpose. See
    .abi/specs/not-implemented/ux/chainlit-plan-review-card.md.
    """
    model_status = model_status or {}
    ordered = plan_execution_order(plan.get("tasks") or [])
    index_of = {t.get("task_id"): i for i, t in enumerate(ordered, 1)}

    steps, deliverables, notices, download_models = [], [], [], []
    for i, task in enumerate(ordered, 1):
        tid = task.get("task_id")
        target = task.get("target") or {}
        agents = [a for a in task.get("agents") or [] if a]
        ms = model_status.get(tid) or {}
        if target.get("tag") and target.get("type", "file") == "file" and target["tag"] not in deliverables:
            deliverables.append(target["tag"])
        if ms.get("model") and not ms.get("location") and ms["model"] not in download_models:
            download_models.append(ms["model"])
        steps.append({
            "task_id": tid,
            "index": i,
            "title": task.get("title") or _fallback_task_title(task),
            "detail": task.get("description", ""),
            "deliverable": {"tag": target["tag"], "type": target.get("type", "file")} if target.get("tag") else None,
            "depends_on": sorted(index_of[d] for d in task.get("dependencies") or [] if d in index_of),
            "agent": (agents[0].get("name") if isinstance(agents[0], dict) else str(agents[0])) if agents else None,
            "direct_tool": task.get("direct_tool"),
            "model": ms.get("model"),
        })

    for model in download_models:
        notices.append({"code": "model_download", "model": model})

    return {
        "objective": plan.get("objective", ""),
        "steps": steps,
        "deliverables": deliverables,
        "notices": notices,
    }


def format_conversation_summary(turns: Optional[list]) -> Optional[str]:
    """Render a recorded conversation window as injectable prompt text.

    Pairs with ``AbiAgent.record_conversation_turn`` — ``turns`` is the
    ``conversation_summary`` list it writes to session context (each item
    ``{"user": ..., "assistant": ...}``). ``None``/empty → ``None`` (nothing
    to inject), same convention as the other contract fields it sits
    alongside (e.g. ``pending_plan_summary``). See
    .abi/specs/orchestrator-conversation-memory.md.
    """
    if not turns:
        return None
    return "\n\n".join(f"User: {t['user']}\nAssistant: {t['assistant']}" for t in turns)


async def yield_chunk_data(chunk: str) -> str:
    """Convert chunk to serializable format
    Args: chunk str.

    yields:
        Formatted string.
    """
    try:
        if hasattr(chunk, 'model_dump'):
            chunk_data = chunk.model_dump()
        elif hasattr(chunk, 'dict'):
            chunk_data = chunk.dict()
        elif hasattr(chunk, '__dict__'):
            chunk_data = chunk.__dict__
        elif isinstance(chunk, dict):
            # AgentResponse yields plain dicts: send them as a JSON object,
            # not str(dict) (a Python repr no JSON client can parse).
            # parse_agent_message already accepts a dict here.
            chunk_data = {"message": chunk, "type": "dict"}
        else:
            chunk_data = {"message": str(chunk), "type": type(chunk).__name__}

        abi_logging(f"[DEBUG] Chunk received: {type(chunk).__name__} - {str(chunk)[:100]}...", level="debug")

        yield (f"data: {json.dumps(chunk_data, ensure_ascii=False, default=str)}\n\n").encode()
    except Exception as serialize_error:
        error_data = {
            "error": "Serialization failed",
            "chunk_type": type(chunk).__name__,
            "details": str(serialize_error)
        }
        yield (f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n").encode()
