"""Builder Agent — Steps.

DAG: parse_spec -> verify_tools -> generate_config -> ensure_model_available
     (tools.py, @agent.tool) -> build_container -> register_card
"""

import json
import os
import time

from app import agent
from abi_core.common.utils import abi_logging
from abi_core.common.semantic_tools import tool_search_tools

@agent.step(
    name="parse_spec",
    input_map={
        "builder_spec": "$input.builder_spec",
        "task_id": "$input.task_id",
        "task_type": "$input.task_type",
        "plan_context_id": "$input.context_id",
    },
)
def parse_spec(builder_spec, task_id, task_type, plan_context_id=""):
    """Parse and validate the builder_spec from the planner.

    Extracts tools needed, tools to create, system prompt, and
    determines the build strategy.

    Rule 6: If spec is malformed, report partial progress.
    """
    abi_logging(f"[📋] Step 1: Parsing builder_spec for task '{task_id}' (type: {task_type})")

    if not builder_spec or not isinstance(builder_spec, dict):
        return {
            "status": "error",
            "message": "Invalid or empty builder_spec",
            "task_id": task_id,
        }

    system_prompt = builder_spec.get("system_prompt", "You are a specialized agent.")
    tools_needed = builder_spec.get("tools", [])
    tools_detail = builder_spec.get("tools_detail", [])
    tools_to_create = builder_spec.get("tools_to_create", [])
    ephemeral = builder_spec.get("ephemeral", True)
    llm_config_override = builder_spec.get("llm_config", {})
    artifact_keys = builder_spec.get("artifact_keys", [])
    target_tag = builder_spec.get("target_tag", "")
    # The run's reviewer (ephemeral-reviewer-pipeline 02.3): same zombie,
    # another role, tied to the plan run. Its model defaults to the
    # integration reviewer's, like the repair it replaces.
    role = (builder_spec.get("role") or "code").strip().lower()
    run_id = builder_spec.get("run_id", "")
    if role == "reviewer" and not llm_config_override.get("model") and os.getenv("INTEGRATION_REVIEWER_MODEL"):
        llm_config_override = {**llm_config_override, "model": os.getenv("INTEGRATION_REVIEWER_MODEL")}

    needs_tool_creation = task_type == "create_tools_and_execute" or len(tools_to_create) > 0

    abi_logging(
        f"[✅] Spec parsed: {len(tools_needed)} tools needed, "
        f"{len(tools_to_create)} to create, ephemeral={ephemeral}"
    )

    return {
        "status": "parsed",
        "task_id": task_id,
        "task_type": task_type,
        "system_prompt": system_prompt,
        "tools_needed": tools_needed,
        "tools_detail": tools_detail,
        "tools_to_create": tools_to_create,
        "needs_tool_creation": needs_tool_creation,
        "ephemeral": ephemeral,
        "llm_config_override": llm_config_override,
        "artifact_keys": artifact_keys,
        "target_tag": target_tag,
        "plan_context_id": plan_context_id,
        "role": role,
        "run_id": run_id,
    }


# ── Step 2: Resolve Tools ──────────────────────────────────────

@agent.step(
    name="verify_tools",
    depends_on=["parse_spec"],
    input_map={"spec": "$parse_spec"},
)
async def verify_tools(spec):
    """Verify all required tools exist in the semantic layer.

    Rule 1: ALWAYS verify tools exist before building.
    Rule 6: Report partial progress (resolved vs missing).
    """
    if spec.get("status") == "error":
        return spec

    task_id = spec["task_id"]
    tools_needed = spec["tools_needed"]

    abi_logging(f"[🔍] Step 2: Verifying {len(tools_needed)} tools for task '{task_id}'")

    resolved = []
    missing = []

    for tool_name in tools_needed:
        matches = await tool_search_tools.ainvoke(tool_name)
        found = any(m["name"] == tool_name for m in matches)
        if found:
            resolved.append(tool_name)
            abi_logging(f"  [✅] '{tool_name}' — found")
        else:
            missing.append(tool_name)
            abi_logging(f"  [❌] '{tool_name}' — NOT found")

    # If tools are missing and we can't create them, fail with partial info
    if missing and not spec["needs_tool_creation"]:
        return {
            "status": "error",
            "message": f"Tools not found and no creation spec: {', '.join(missing)}",
            "tools_resolved": resolved,
            "tools_missing": missing,
            "task_id": task_id,
        }

    abi_logging(
        f"[✅] Verification complete: {len(resolved)} resolved, "
        f"{len(missing)} missing, {len(spec['tools_to_create'])} to create"
    )

    return {
        **spec,
        "status": "verified",
        "tools_resolved": resolved,
        "tools_missing": missing,
    }


# ── Step 3a: Generate Config ───────────────────────────────────

@agent.step(
    name="generate_config",
    depends_on=["verify_tools"],
    input_map={"verification": "$verify_tools"},
)
def generate_config(verification):
    """Generate unique agent name, port, and full configuration.

    Rule 2: Unique names with task_id + timestamp.
    Rule 3: Inherit builder's LLM config unless overridden.
    """
    if verification.get("status") == "error":
        return verification

    task_id = verification["task_id"]
    timestamp = int(time.time())
    role = verification.get("role", "code")
    run_id = verification.get("run_id", "")
    if role == "reviewer":
        if not run_id:
            return {"status": "error", "message": "a reviewer needs the plan's run_id", "task_id": task_id}
        # Known name: code agents find their run's reviewer by it (02.2).
        agent_name = f"reviewer-{run_id}"
    elif run_id:
        # The run's id in the name: the A2A policy allows ephemeral-<run_id>-*
        # <-> reviewer-<run_id> only (same run), user decision 2026-10-10.
        agent_name = f"ephemeral-{run_id}-{task_id}-{timestamp}".replace("_", "-")
    else:
        agent_name = f"ephemeral-{task_id}-{timestamp}".replace("_", "-")
    port = 11440 + (hash(agent_name) % 100)

    abi_logging(f"[🔧] Step 3a: Generating config for '{agent_name}' on port {port}")

    config = {
        "status": "configured",
        "agent_name": agent_name,
        "agent_display_name": f"Ephemeral Agent ({task_id})",
        "port": port,
        "system_prompt": verification["system_prompt"],
        "tools_resolved": verification["tools_resolved"],
        "tools_detail": verification.get("tools_detail", []),
        "tools_to_create": verification.get("tools_to_create", []),
        "tools_missing": verification.get("tools_missing", []),
        "needs_tool_creation": verification.get("needs_tool_creation", False),
        "ephemeral": verification["ephemeral"],
        "llm_config_override": verification.get("llm_config_override", {}),
        "task_id": task_id,
        "task_type": verification["task_type"],
        "artifact_keys": verification.get("artifact_keys", []),
        "target_tag": verification.get("target_tag", ""),
        "plan_context_id": verification.get("plan_context_id", ""),
        "role": role,
        "run_id": run_id,
        # Library tools — all BASE_TOOLS for ephemeral agents
        "library_tools_resolved": ["write_file", "read_file", "run_shell", "list_files"],
    }

    # Pre-build agent card JSON so the ephemeral can write it to disk.
    # container_url: Docker DNS locally, the run.app URL on Cloud Run —
    # deterministic, so it is known before the ephemeral exists.
    from abi_core.common.container_runtime import container_url

    card = {
        "id": f"agent://{agent_name}",
        "name": agent_name,
        "description": f"Ephemeral agent for task {task_id}",
        "url": container_url(agent_name, port),
        "version": "1.0.0",
        "auth": {
            "method": "hmac_sha256",
            "key_id": f"agent://{agent_name}-default",
            "shared_secret": f"ephemeral-{agent_name}-{task_id}",
        },
    }
    card.update(_role_card_fields(role, run_id))
    config["agent_card_json"] = json.dumps(card)

    abi_logging(f"[✅] Config generated: {agent_name}")
    return config


def _role_card_fields(role: str, run_id: str) -> dict:
    """Card fields of the run's reviewer: the sandbox permission the
    abi/sandbox policy checks (only as reviewer-<run_id>, 02.5)."""
    if role != "reviewer":
        return {}
    return {
        "description": f"Reviewer of plan run {run_id}",
        "security": {"allowed_actions": ["run_sandbox"]},
        "metadata": {"role": "reviewer", "run_id": run_id},
    }


def _role_env(config: dict) -> dict:
    """Env of the run's reviewer: its role, its run, the governed sandbox."""
    if config.get("role") != "reviewer":
        return {}
    return {
        "ZOMBIE_ROLE": "reviewer",
        "RUN_ID": config.get("run_id", ""),
        "SANDBOX_RUNTIME": "service",
        "SANDBOX_SERVICE_URL": os.getenv("SANDBOX_SERVICE_URL", ""),
    }


def _ephemeral_llm_params_env(eph_provider: str, override: dict) -> dict:
    """The ephemeral's LLM_EXTRA_PARAMS / LLM_TEMPERATURE.

    EPHEMERAL_LLM_EXTRA_PARAMS (a JSON object) first; without it, the
    Builder's own LLM_EXTRA_PARAMS only when the ephemeral runs on the same
    provider — the parameters are provider-specific. The task's
    builder_spec["llm_config"] goes on top: its extra_params win, and its
    temperature becomes LLM_TEMPERATURE. Invalid JSON raises ValueError.
    See .abi/specs/implemented/llm-params-from-config.md."""
    from abi_core.agent.llm_provider import parse_extra_params

    builder_provider = (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()
    if os.getenv("EPHEMERAL_LLM_EXTRA_PARAMS"):
        params = parse_extra_params(os.getenv("EPHEMERAL_LLM_EXTRA_PARAMS"), "EPHEMERAL_LLM_EXTRA_PARAMS")
    elif eph_provider == builder_provider:
        params = parse_extra_params(os.getenv("LLM_EXTRA_PARAMS"))
    else:
        params = {}

    task_params = override.get("extra_params") or {}
    if not isinstance(task_params, dict):
        raise ValueError(f"builder_spec llm_config.extra_params must be an object, got {type(task_params).__name__}")
    params = {**params, **task_params}

    env = {"LLM_EXTRA_PARAMS": json.dumps(params)} if params else {}
    if override.get("temperature") is not None:
        env["LLM_TEMPERATURE"] = str(float(override["temperature"]))
    return env


# ── Step 3b: Build Container ───────────────────────────────────

@agent.step(
    name="build_container",
    depends_on=["ensure_model_available"],
    input_map={"config": "$ensure_model_available"},
)
async def build_container(config):
    """Clone the zombie container with custom env vars via container_runtime."""
    if config.get("status") == "error":
        return config

    from abi_core.common.container_runtime import container_url, run_container

    # Ephemerals can run on a different LLM provider than the Builder itself
    # (e.g. Ollama for the swarm, Gemini for ephemerals) — EPHEMERAL_LLM_*
    # override the Builder's own LLM_* for the ephemeral only.
    # `or`, not a getenv default: compose passes an unset var as "".
    eph_provider = (os.getenv("EPHEMERAL_LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "ollama").strip().lower()
    # Provider SDKs are optional extras of abi-core-ai named after the
    # provider; the ephemeral image only has Ollama's.
    eph_extra = f"[{eph_provider}]" if eph_provider in {
        "gemini", "openai", "anthropic", "grok", "bedrock", "vertex"} else ""
    eph_llm_env = {"LLM_PROVIDER": eph_provider}
    if eph_provider != "ollama":
        # Hosted provider: the ephemeral needs the key (and an endpoint only
        # if one is set). Accepted risk while ephemerals still have run_shell
        # and network: use a dedicated, rate-limited key for ephemerals.
        eph_llm_env["LLM_API_KEY"] = os.getenv("EPHEMERAL_LLM_API_KEY") or os.getenv("LLM_API_KEY", "")
        if os.getenv("EPHEMERAL_LLM_BASE_URL"):
            eph_llm_env["LLM_BASE_URL"] = os.getenv("EPHEMERAL_LLM_BASE_URL")
    eph_llm_env.update(_ephemeral_llm_params_env(eph_provider, config.get("llm_config_override") or {}))

    agent_name = config["agent_name"]
    port = config["port"]
    tools_json = json.dumps(config["tools_resolved"])

    # Resolve artifact keys and target tag from builder_spec
    artifact_keys = config.get("artifact_keys", [])
    artifact_keys_json = json.dumps(artifact_keys)

    abi_logging(f"[🐳] Step 3b: Cloning zombie as '{agent_name}' on port {port}")

    # Zombie package path after pip install
    zombie_pkg = "abi_agents/zombie/agent"
    site_packages = "/opt/venv/lib/python3.12/site-packages"

    result = await run_container(
        name=agent_name,
        image=os.getenv("ABI_IMAGE", "agentbase/abi-image-v2:latest"),
        env_vars={
            "ZOMBIE_MODE": "active",
            "AGENT_NAME": agent_name,
            "AGENT_PORT": str(port),
            "AGENT_HOST": "0.0.0.0",
            "SYSTEM_PROMPT": config["system_prompt"],
            "TOOLS": tools_json,
            "LIBRARY_TOOLS": json.dumps(config.get("library_tools_resolved", [])),
            "ARTIFACT_KEYS": artifact_keys_json,
            # The model ensure_model_available resolved (and pulled) for this
            # task — a builder_spec["llm_config"]["model"] override, else
            # EPHEMERAL_MODEL_NAME. It used to read the env var directly, so
            # a per-task override was pulled and then never used.
            "MODEL_NAME": config.get("model_used") or os.getenv(
                "EPHEMERAL_MODEL_NAME", os.getenv("MODEL_NAME", "qwen3:latest")),
            "OLLAMA_HOST": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            **eph_llm_env,
            "MCP_HOST": os.getenv("MCP_HOST", "localhost"),
            "MCP_PORT": os.getenv("MCP_PORT", "10100"),
            "MCP_TRANSPORT": os.getenv("MCP_TRANSPORT", "streamable-http"),
            "SEMANTIC_LAYER_HOST": os.getenv("SEMANTIC_LAYER_HOST", ""),
            # The A2A validator checks every outgoing call against Guardian/OPA.
            # Without these it went to localhost and, in strict mode, denied
            # every call an ephemeral made (send_link, the reviewer's
            # questions) — live 2026-10-09. Ephemerals only received calls
            # before the reviewer pipeline.
            **{k: os.environ[k] for k in ("OPA_URL", "GUARDIAN_URL") if os.environ.get(k)},
            "ARTIFACT_ENDPOINT": os.getenv("ARTIFACT_ENDPOINT", ""),
            "ARTIFACT_ACCESS_KEY": os.getenv("ARTIFACT_ACCESS_KEY", ""),
            "ARTIFACT_SECRET_KEY": os.getenv("ARTIFACT_SECRET_KEY", ""),
            "ARTIFACT_BUCKET": os.getenv("ARTIFACT_BUCKET", "abi-artifacts"),
            "LOG_TO_ARTIFACT_STORE": os.getenv("LOG_TO_ARTIFACT_STORE", "true"),
            "LOG_BUCKET": os.getenv("LOG_BUCKET", "abi-logs"),
            "AGENT_CARD_JSON": config.get("agent_card_json", ""),
            "CONTEXT_ID": config.get("task_id", ""),
            # process-awareness.md (Tier 3) — the plan-wide id, distinct
            # from CONTEXT_ID (this task's own id). The ephemeral reads
            # this back via get_session_context to learn its place in the
            # overall plan (objective, sibling tasks, dependencies).
            "PLAN_CONTEXT_ID": config.get("plan_context_id", ""),
            # Same session backend the Orchestrator writes process_context
            # and inter-task contracts to. Without these the ephemeral fell
            # back to an in-memory backend — its reads of PLAN_CONTEXT_ID /
            # dependency contracts always came back empty, and the contract
            # it wrote on completion died with the container. Confirmed
            # live 2026-10-03: never worked in production since the feature
            # shipped. See .abi/fixes/2026-10-03-cross-file-integration-context.md.
            "SESSION_BACKEND": os.getenv("SESSION_BACKEND", "memory"),
            "SESSION_REDIS_URL": os.getenv("SESSION_REDIS_URL", os.getenv("REDIS_URL", "")),
            "AGENT_MEMORY_URL": os.getenv("AGENT_MEMORY_URL", "http://abi-swarm-agent-memory:8000"),
            "SERVICE_MODULE": "",
            "SERVICE_COMMAND": (
                f"pip install --quiet --no-cache-dir --upgrade 'abi-core-ai{eph_extra}' && "
                f"cp -r {site_packages}/{zombie_pkg}/* /app/ && "
                f"python3 main.py"
            ),
            "PYTHONPATH": "/app",
            **_role_env(config),
        },
        network=os.getenv("DOCKER_NETWORK", "abi_network"),
        port=port,
        health_check_url=f"{container_url(agent_name, port)}/health",
        # Generous on purpose: the start-up pip install alone took 69s live
        # (2026-10-05) and a 60s budget aborted a healthy ephemeral. The
        # wait ends early if the container dies (check_container_health),
        # so a broken start-up still fails fast.
        health_timeout=int(os.getenv("EPHEMERAL_HEALTH_TIMEOUT", "300")),
    )

    if result["status"] in ("error", "unhealthy"):
        # Don't leave it behind: an unhealthy ephemeral was found still
        # running 22 minutes after the Builder gave up on it.
        if result["status"] == "unhealthy":
            from abi_core.common.container_runtime import destroy_container
            await destroy_container(agent_name)
        return {
            "status": "error",
            "message": result.get("error", f"Container '{agent_name}' is {result['status']} (health check failed)"),
            "agent_name": agent_name,
            "task_id": config["task_id"],
        }

    return {
        "status": "built",
        "agent_name": agent_name,
        "container_id": result.get("container_id", ""),
        "port": port,
        "url": result.get("url") or container_url(agent_name, port),
        "system_prompt": config["system_prompt"],
        "tools_resolved": config["tools_resolved"],
        "tools_created": [],
        "ephemeral": config["ephemeral"],
        "task_id": config["task_id"],
        "role": config.get("role", "code"),
        "run_id": config.get("run_id", ""),
    }


# ── Step 4: Register Agent Card ────────────────────────────────

@agent.step(
    name="register_card",
    depends_on=["build_container"],
    input_map={"build_result": "$build_container"},
)
async def register_card(build_result):
    """Register the ephemeral agent card in the semantic layer via MCP."""
    if build_result.get("status") == "error":
        return build_result

    from abi_core.common.semantic_tools import tool_register_agent

    agent_name = build_result["agent_name"]
    url = build_result["url"]
    task_id = build_result["task_id"]

    abi_logging(f"[📋] Step 4: Registering agent card for '{agent_name}'")

    agent_card = {
        "id": f"agent://{agent_name}",
        "name": agent_name,
        "description": f"Ephemeral agent for task {task_id}",
        "url": url,
        "version": "1.0.0",
        "capabilities": {
            "streaming": "True",
            "pushNotifications": "False",
            "stateTransitionHistory": "False",
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{
            "id": "execute_task",
            "name": f"Execute {task_id}",
            "description": build_result["system_prompt"][:200],
            "tags": build_result["tools_resolved"],
        }],
        "ephemeral": True,
        "destroy_after_task": True,
        "auth": {
            "method": "hmac_sha256",
            "key_id": f"agent://{agent_name}-default",
            "shared_secret": f"ephemeral-{agent_name}-{task_id}",
        },
    }
    agent_card.update(_role_card_fields(build_result.get("role", "code"), build_result.get("run_id", "")))

    # Register in semantic layer via MCP
    try:
        reg_result = await tool_register_agent.ainvoke({"agent_card_dict": agent_card})
        if isinstance(reg_result, dict) and reg_result.get("success"):
            abi_logging(f"[✅] Agent card registered in semantic layer: {agent_name}")
        else:
            abi_logging(f"[⚠️] Registration response: {reg_result}")
    except Exception as e:
        abi_logging(f"[⚠️] Could not register in semantic layer: {e}")
        # Continue anyway — the agent can still work via direct A2A

    return {
        "status": "ready",
        "agent": {
            "name": agent_name,
            "url": url,
            "port": build_result["port"],
            "ephemeral": True,
            "destroy_after_task": True,
        },
        "tools_resolved": build_result["tools_resolved"],
        "tools_created": build_result.get("tools_created", []),
        "agent_card": agent_card,
        "task_id": task_id,
    }


# Step 5 (Cleanup) is triggered by the orchestrator after task execution.
# Not part of this DAG — it's a separate signal/command.
