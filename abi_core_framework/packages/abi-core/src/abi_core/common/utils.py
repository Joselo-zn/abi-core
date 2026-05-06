import logging
import os 
import sys
import json
import threading
from datetime import datetime, timezone

from typing import Any
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

# Parse SEMANTIC_LAYER_HOST which may contain protocol and port
SEMANTIC_LAYER_URL = os.getenv('SEMANTIC_LAYER_HOST', 'http://abi-semantic-layer:10100')
# MCP_TRANSPORT supports 'sse' or 'streamable-http'
MCP_TRANSPORT = os.getenv('MCP_TRANSPORT', 'streamable-http')

# Extract host and port from URL if provided with protocol
# Supports formats: http://host:port/path or just host
url_match = re.match(r'https?://([^:/]+)(?::(\d+))?', SEMANTIC_LAYER_URL)
if url_match:
    HOST = url_match.group(1)
    PORT = int(url_match.group(2)) if url_match.group(2) else 10100
    URL = SEMANTIC_LAYER_URL
else:
    # Fallback: treat as plain hostname
    HOST = SEMANTIC_LAYER_URL.split(':')[0]
    PORT = int(os.getenv('SEMANTIC_LAYER_PORT', 10100))
    URL = f'http://{HOST}:{PORT}'

def get_mcp_server_config() -> ServerConfig:
    """Get the MCP server configuration.
    
    Parses SEMANTIC_LAYER_HOST environment variable which can be:
    - Full URL: http://hostname:port
    - Hostname only: hostname (uses SEMANTIC_LAYER_PORT or default 10100)
    
    Transport can be configured via MCP_TRANSPORT environment variable:
    - 'sse' (default): Server-Sent Events transport
    - 'streamable-http': Streamable HTTP transport
    
    Returns:
        ServerConfig with parsed host, port, transport, and url
    """
    abi_logging(f'[*] MCP Config: Host={HOST}, Port={PORT}, Transport={MCP_TRANSPORT}')
    return ServerConfig(
        host=HOST,
        port=PORT,
        transport=MCP_TRANSPORT,
        url=URL,
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


def format_plan_summary(plan: dict) -> str:
    """Format a plan dict into a human-readable markdown summary.

    Args:
        plan: Dict with ``objective``, ``tasks``, ``execution_strategy``.

    Returns:
        Formatted string.
    """
    objective = plan.get("objective", "Complete user request")
    tasks = plan.get("tasks", [])
    strategy = plan.get("execution_strategy", "sequential")

    lines = [
        "📋 **Plan Created**\n",
        f"🎯 **Objective:** {objective}\n",
        f"📊 **Strategy:** {strategy.capitalize()}\n",
        f"**Tasks ({len(tasks)}):**\n",
    ]

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
            lines.append("   ⚠️ No agent assigned")
        if deps:
            lines.append(f"   🔗 Depends on: {', '.join(deps)}")

    lines.append("\n✅ Plan ready for execution by Orchestrator")
    return "\n".join(lines)


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
        else:
            chunk_data = {"message": str(chunk), "type": type(chunk).__name__}

        abi_logging(f"[DEBUG] Chunk received: {type(chunk).__name__} - {str(chunk)[:100]}...", level="debug")

        yield (f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n").encode()
    except Exception as serialize_error:
        error_data = {
            "error": "Serialization failed",
            "chunk_type": type(chunk).__name__,
            "details": str(serialize_error)
        }
        yield (f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n").encode()
