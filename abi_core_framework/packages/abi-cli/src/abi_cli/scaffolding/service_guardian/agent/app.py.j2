"""Guardian Agent — AbiCore instance with @agent.step DAG.

The Guardian validates actions against OPA policies before any agent
in the swarm can execute. Its DAG:

    parse_request → evaluate_policy → format_decision

For workflow validation (multiple actions), the task orchestrates
sequential policy checks.
"""

from abi_core.agent import AbiCore
from abi_core.agent.agent_response import AgentResponse

from config import config

agent = AbiCore()


# ── Steps ───────────────────────────────────────────────────────

@agent.step(name="parse_request", input_map={"query": "$input.query"})
async def parse_request(query: str) -> dict:
    """Parse incoming validation request (JSON or plain text)."""
    import json

    try:
        request_data = json.loads(query) if isinstance(query, str) else query
        if not isinstance(request_data, dict):
            request_data = {"query": query, "action": "unknown", "resource_type": "unknown"}
    except (json.JSONDecodeError, TypeError):
        request_data = {"query": query, "action": "unknown", "resource_type": "unknown"}

    return {
        "action": request_data.get("action", "unknown"),
        "resource_type": request_data.get("resource_type", "unknown"),
        "source_agent": request_data.get("source_agent", "unknown"),
        "target_agent": request_data.get("target_agent"),
        "content": request_data.get("content"),
        "metadata": request_data.get("metadata", {}),
        "raw_request": request_data,
    }


@agent.step(
    name="evaluate_policy",
    depends_on=["parse_request"],
    input_map={
        "action": "$parse_request.result.action",
        "resource_type": "$parse_request.result.resource_type",
        "source_agent": "$parse_request.result.source_agent",
        "target_agent": "$parse_request.result.target_agent",
        "content": "$parse_request.result.content",
        "metadata": "$parse_request.result.metadata",
    },
)
async def evaluate_policy(
    action: str,
    resource_type: str,
    source_agent: str,
    target_agent=None,
    content=None,
    metadata=None,
) -> dict:
    """Evaluate action against OPA policies via the secure policy engine."""
    from abi_agents.guardian.agent.policy_engine_secure import get_secure_policy_engine

    engine = get_secure_policy_engine()

    if not engine.security_validated:
        return {
            "allow": False,
            "deny": True,
            "risk_score": 1.0,
            "reason": "System security not validated",
            "remediation": ["Initialize system security", "Contact administrator"],
        }

    decision = await engine.evaluate_policy(
        action=action,
        resource_type=resource_type,
        source_agent=source_agent,
        target_agent=target_agent,
        content=content,
        metadata=metadata,
    )

    return {
        "allow": decision.allow,
        "deny": decision.deny,
        "risk_score": decision.risk_score,
        "rules_evaluated": decision.rules_evaluated,
        "remediation": decision.remediation_suggestions,
        "audit_log": decision.audit_log,
    }


@agent.step(
    name="format_decision",
    depends_on=["evaluate_policy"],
    input_map={"decision": "$evaluate_policy.result"},
)
async def format_decision(decision: dict) -> dict:
    """Format the policy decision for the caller."""
    risk_level = config.get_risk_level(decision["risk_score"])

    return {
        "policy_decision": {
            "allow": decision["allow"],
            "deny": decision["deny"],
            "risk_score": decision["risk_score"],
            "risk_level": risk_level,
            "rules_evaluated": decision.get("rules_evaluated", []),
            "remediation": decision.get("remediation", []),
        },
        "validation_complete": True,
        "security_status": "validated",
    }


# ── Task: Workflow Validation ───────────────────────────────────

@agent.task(name="validate_workflow", task_id="task-guardian-workflow")
async def validate_workflow(query: str):
    """Validate a multi-action workflow against policies.

    Receives a JSON with {"actions": [...], "executing_agent": "..."}.
    Evaluates each action and returns aggregate decision.
    """
    import json

    yield AgentResponse.status("Parsing workflow...")

    try:
        workflow_data = json.loads(query) if isinstance(query, str) else query
    except (json.JSONDecodeError, TypeError):
        yield AgentResponse.error("Invalid workflow format — expected JSON with 'actions' array")
        return

    actions = workflow_data.get("actions", [])
    executing_agent = workflow_data.get("executing_agent", "unknown")

    if not actions:
        yield AgentResponse.error("No actions in workflow to validate")
        return

    yield AgentResponse.status(f"Validating {len(actions)} actions...")

    blocked = []
    high_risk = []
    total_risk = 0.0

    for action_data in actions:
        result = await agent.execute_step(
            "evaluate_policy",
            action=action_data.get("type", "unknown"),
            resource_type=action_data.get("resource_type", "unknown"),
            source_agent=executing_agent,
            target_agent=action_data.get("target_agent"),
            content=str(action_data),
            metadata={"workflow_step": action_data.get("step", 0)},
        )

        total_risk += result["risk_score"]
        if result["deny"]:
            blocked.append(action_data)
        elif result["risk_score"] > config.HIGH_RISK_THRESHOLD:
            high_risk.append(action_data)

    avg_risk = total_risk / len(actions) if actions else 0.0
    workflow_allowed = len(blocked) == 0 and avg_risk < config.HIGH_RISK_THRESHOLD

    yield AgentResponse.result({
        "workflow_allowed": workflow_allowed,
        "total_actions": len(actions),
        "blocked_actions": len(blocked),
        "high_risk_actions": len(high_risk),
        "average_risk": round(avg_risk, 3),
        "risk_level": config.get_risk_level(avg_risk),
    })
