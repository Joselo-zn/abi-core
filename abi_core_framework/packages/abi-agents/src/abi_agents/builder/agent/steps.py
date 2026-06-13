"""Builder Agent — Steps.

DAG: parse_spec -> verify_tools -> generate_config -> build_container -> register_card
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
    },
)
def parse_spec(builder_spec, task_id, task_type):
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
        # Library tools — all BASE_TOOLS for ephemeral agents
        "library_tools_resolved": ["write_file", "read_file", "run_shell", "list_files"],
    }

    # Pre-build agent card JSON so the ephemeral can write it to disk
    config["agent_card_json"] = json.dumps({
        "id": f"agent://{agent_name}",
        "name": agent_name,
        "description": f"Ephemeral agent for task {task_id}",
        "url": f"http://{agent_name}:{port}",
        "version": "1.0.0",
        "auth": {
            "method": "hmac_sha256",
            "key_id": f"agent://{agent_name}-default",
            "shared_secret": f"ephemeral-{agent_name}-{task_id}",
        },
    })

    abi_logging(f"[✅] Config generated: {agent_name}")
    return config


# ── Step 3b: Build Container ───────────────────────────────────

@agent.step(
    name="build_container",
    depends_on=["generate_config"],
    input_map={"config": "$generate_config"},
)
async def build_container(config):
    """Clone the zombie container with custom env vars via container_runtime."""
    if config.get("status") == "error":
        return config

    from abi_core.common.container_runtime import run_container

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
            "MODEL_NAME": os.getenv("EPHEMERAL_MODEL_NAME", os.getenv("MODEL_NAME", "devstral:24b")),
            "OLLAMA_HOST": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "ollama"),
            "MCP_HOST": os.getenv("MCP_HOST", "localhost"),
            "MCP_PORT": os.getenv("MCP_PORT", "10100"),
            "MCP_TRANSPORT": os.getenv("MCP_TRANSPORT", "streamable-http"),
            "SEMANTIC_LAYER_HOST": os.getenv("SEMANTIC_LAYER_HOST", ""),
            "ARTIFACT_ENDPOINT": os.getenv("ARTIFACT_ENDPOINT", ""),
            "ARTIFACT_ACCESS_KEY": os.getenv("ARTIFACT_ACCESS_KEY", ""),
            "ARTIFACT_SECRET_KEY": os.getenv("ARTIFACT_SECRET_KEY", ""),
            "ARTIFACT_BUCKET": os.getenv("ARTIFACT_BUCKET", "abi-artifacts"),
            "LOG_TO_ARTIFACT_STORE": os.getenv("LOG_TO_ARTIFACT_STORE", "true"),
            "LOG_BUCKET": os.getenv("LOG_BUCKET", "abi-logs"),
            "AGENT_CARD_JSON": config.get("agent_card_json", ""),
            "CONTEXT_ID": config.get("task_id", ""),
            "AGENT_MEMORY_URL": os.getenv("AGENT_MEMORY_URL", "http://abi-swarm-agent-memory:8000"),
            "SERVICE_MODULE": "",
            "SERVICE_COMMAND": (
                f"pip install --quiet --no-cache-dir --upgrade abi-core-ai && "
                f"cp -r {site_packages}/{zombie_pkg}/* /app/ && "
                f"python3 main.py"
            ),
            "PYTHONPATH": "/app",
        },
        network=os.getenv("DOCKER_NETWORK", "abi_network"),
        port=port,
        health_check_url=f"http://{agent_name}:{port}/health",
        health_timeout=60,
    )

    if result["status"] in ("error", "unhealthy"):
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
        "url": result.get("url", f"http://{agent_name}:{port}"),
        "system_prompt": config["system_prompt"],
        "tools_resolved": config["tools_resolved"],
        "tools_created": [],
        "ephemeral": config["ephemeral"],
        "task_id": config["task_id"],
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
