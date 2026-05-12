"""
Guardian Agent — Security policy enforcement for the ABI swarm.

Validates actions against OPA policies before any agent can execute.
Provides health checks, emergency shutdown, and MCP evaluation interface.
"""

import json
import logging
from typing import Dict, Any, Optional
from collections.abc import AsyncIterable
from datetime import datetime

from abi_core.common.utils import abi_logging
from abi_core.common import prompts
from abi_core.agent.agent import AbiAgent
from abi_core.agent.agent_response import AgentResponse

from config.config import config

logger = logging.getLogger(__name__)


class AbiGuardianAgent(AbiAgent):
    """Guardian Agent — security gate for the ABI swarm.

    The execution DAG (parse_request → evaluate_policy → format_decision)
    is registered in app.py via @agent.step decorators.

    This class adds:
    - Security initialization and health checks
    - Emergency shutdown mechanism
    - MCP evaluation interface for semantic layer
    - Custom stream() with security pre-checks
    """

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            llm_config=config.LLM_CONFIG,
            tools=[],
            system_prompt=prompts.GUARDIAL_COT_INSTRUCTIONS,
            content_types=["text", "text/plain", "application/json"],
        )
        self.system_secure = False
        self.emergency_mode = False

    async def initialize_security(self) -> bool:
        """Initialize and validate system security.

        Returns True if the system is secure and can operate.
        Must be called before the agent starts accepting requests.
        """
        from abi_agents.guardian.agent.policy_engine_secure import get_secure_policy_engine

        try:
            abi_logging("🔒 Initializing Guardian Security System...")
            engine = get_secure_policy_engine()
            await engine.initialize()

            health = await engine.health_check()
            if not health.get("system_secure", False):
                abi_logging("🚨 CRITICAL: System security validation FAILED", level="error")
                return False

            self.system_secure = True
            abi_logging("✅ Guardian Security System VALIDATED")
            return True

        except Exception as e:
            abi_logging(f"🚨 Security initialization failed: {e}", level="error")
            return False

    async def stream(
        self, query: str, session_id: str, task_id: str
    ) -> AsyncIterable[Dict[str, Any]]:
        """Stream policy validation with mandatory security pre-check."""

        if not self.system_secure:
            yield AgentResponse.error(
                "🚨 CRITICAL: Guardian security not validated — system blocked"
            )
            return

        if self.emergency_mode:
            yield AgentResponse.error(
                "🚨 System in emergency mode — all operations blocked"
            )
            return

        # Check if this is a workflow validation (has "actions" key)
        try:
            parsed = json.loads(query) if isinstance(query, str) else query
            if isinstance(parsed, dict) and "actions" in parsed:
                # Delegate to workflow task
                if hasattr(self, "_registered_tasks") and "validate_workflow" in self._registered_tasks:
                    task_entry = self._registered_tasks["validate_workflow"]
                    async for chunk in task_entry.fn(query=query):
                        yield chunk
                    return
        except (json.JSONDecodeError, TypeError):
            pass

        # Default: execute the DAG (parse → evaluate → format)
        yield AgentResponse.status(
            "Validating...",
            agent=self.agent_name,
            context_id=session_id,
            task_id=task_id,
        )

        if self.tool_graph is not None:
            input_data = {"query": query, "context_id": session_id, "task_id": task_id}

            dag_result, heartbeats = await self._run_with_heartbeat(
                self.tool_graph.execute(input_data),
                session_id,
                task_id,
                "Evaluating policies...",
            )
            for hb in heartbeats:
                yield hb

            if dag_result.get("failed_node"):
                yield AgentResponse.error(dag_result.get("error", "Policy evaluation failed"))
                return

            outputs = dag_result.get("node_outputs", {})
            decision = outputs.get("format_decision", {})

            yield AgentResponse.success(
                decision,
                agent=self.agent_name,
                context_id=session_id,
                task_id=task_id,
            )
        else:
            yield AgentResponse.error("Guardian DAG not initialized")

    async def emergency_shutdown(self, reason: str, initiated_by: str) -> Dict[str, Any]:
        """Emergency shutdown — blocks all operations immediately."""
        abi_logging(f"🚨 EMERGENCY SHUTDOWN by {initiated_by}: {reason}", level="error")

        self.emergency_mode = True
        self.system_secure = False

        return {
            "shutdown_initiated": True,
            "reason": reason,
            "initiated_by": initiated_by,
            "timestamp": datetime.utcnow().isoformat(),
            "system_blocked": True,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with security validation."""
        from abi_agents.guardian.agent.policy_engine_secure import get_secure_policy_engine

        engine = get_secure_policy_engine()
        policy_health = await engine.health_check()

        return {
            **policy_health,
            "guardian_agent": "healthy" if self.system_secure else "SECURITY_NOT_VALIDATED",
            "system_secure": self.system_secure,
            "emergency_mode": self.emergency_mode,
            "overall_status": (
                "SECURE_AND_OPERATIONAL"
                if self.system_secure
                and policy_health.get("core_policies_present")
                and policy_health.get("opa_status") == "healthy"
                else "SECURITY_ISSUES_DETECTED"
            ),
        }
