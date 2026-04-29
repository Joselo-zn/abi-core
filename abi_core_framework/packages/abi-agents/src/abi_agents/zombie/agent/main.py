#!/usr/bin/env python3
"""Zombie Agent — Ephemeral self-configuring agent.

DAG:
  gather_context → analyze_and_execute → synthesize_and_report

Phase 1 (gather_context): Deterministic. Pull artifacts, prepare context.
Phase 2 (analyze_and_execute): LLM autonomous with tools.
Phase 3 (synthesize_and_report): Deterministic. Upload artifacts.
"""

import os
import time

from abi_core.agent import AbiCore
from abi_core.common.utils import abi_logging
from abi_agents.zombie.agent.zombie import ZombieAgent, ZOMBIE_TOOLS
from abi_agents.zombie.agent.config.config import config

# ── Idle mode ──────────────────────────────────────────────────

if config.ZOMBIE_MODE == "idle":
    abi_logging(f"[🧟] Zombie '{config.AGENT_NAME}' in IDLE mode")
    while True:
        time.sleep(60)

# ── Active mode ────────────────────────────────────────────────

abi_logging(f"[🧟→🤖] Zombie activating as '{config.AGENT_NAME}'")
abi_logging(f"[🔧] Tools: {config.TOOL_NAMES}")
abi_logging(f"[🔌] Port: {config.AGENT_PORT}")

agent = AbiCore(config=config, agent_card=config.build_agent_card())


@agent.step(
    name="gather_context",
    input_map={"query": "$input.query"},
)
async def gather_context(query):
    """Phase 1: Pull specific artifacts from MinIO, prepare workspace."""
    from abi_core.common.context_loader import load_agent_context

    ctx = await load_agent_context(
        artifact_keys=config.ARTIFACT_KEYS if config.ARTIFACT_KEYS else None,
        workspace=config.WORKSPACE,
    )
    return {
        "query": query,
        "workspace": config.WORKSPACE,
        "artifacts": ctx["artifacts"],
        "tools_available": config.TOOL_NAMES,
        "system_prompt": config.SYSTEM_PROMPT,
    }


@agent.step(
    name="analyze_and_execute",
    input_map={"context": "$gather_context", "query": "$input.query"},
    depends_on=["gather_context"],
)
async def analyze_and_execute(context, query):
    """Phase 2: LLM autonomous execution with tools."""
    from abi_core.agent.llm_provider import invoke
    from abi_core.common.context_loader import build_execution_prompt

    execution_prompt = build_execution_prompt(
        query=query,
        tools=ZOMBIE_TOOLS,
        artifacts=context.get("artifacts", []),
        workspace=config.WORKSPACE,
    )
    result = await invoke(
        config.LLM_CONFIG, execution_prompt,
        tools=ZOMBIE_TOOLS, system_prompt=config.SYSTEM_PROMPT,
    )
    return {"result": result, "query": query}


@agent.step(
    name="synthesize_and_report",
    input_map={"execution_result": "$analyze_and_execute", "context": "$gather_context"},
    depends_on=["analyze_and_execute"],
)
async def synthesize_and_report(execution_result, context):
    """Phase 3: Upload generated artifacts and flush logs."""
    from abi_core.common.artifact_store import upload_workspace_artifacts

    uploaded_artifacts = await upload_workspace_artifacts(
        agent_name=config.AGENT_NAME,
        workspace=config.WORKSPACE,
        exclude=context.get("artifacts", []),
    )

    return {
        "status": "completed",
        "result": execution_result.get("result", ""),
        "uploaded_artifacts": uploaded_artifacts,
        "agent": config.AGENT_NAME,
    }


# ── Post-response cleanup ──────────────────────────────────────

async def _post_response_cleanup():
    """Cleanup after A2A response is sent: deregister + exit."""
    from abi_core.common.context_loader import self_deregister
    await self_deregister(agent_name=config.AGENT_NAME, destroy=True)


def run_zombie():
    """Entry point for abi-zombie command."""
    zombie = ZombieAgent()
    if os.getenv("EPHEMERAL_SELF_DESTROY", "true").lower() == "true":
        zombie.on_response_sent = _post_response_cleanup
    agent.run(zombie)


if __name__ == "__main__":
    run_zombie()
