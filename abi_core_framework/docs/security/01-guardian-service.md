# Guardian Service

Guardian is the security gate. Every request can be checked against your rules before it runs.

## What it does

- Checks if a request is allowed before executing it
- Evaluates security rules (allow, deny, or require approval)
- Logs all decisions for auditing
- Provides a monitoring dashboard

## Components

| Service | Port | Role |
|---------|------|------|
| Guardian Agent | 11438 | Receives validation requests, calls OPA, returns decisions |
| OPA | 8181 | Evaluates Rego policies, returns allow/deny |
| Dashboard | 8080 | Web UI for monitoring security events |

## Add Guardian to your project

```bash
abi-core create project my-app --with-guardian
```

Or add to an existing project:

```bash
abi-core add service guardian-native
```

## How the Orchestrator uses it

In the Orchestrator's DAG, `guardian_validate` runs in parallel with `classify_query`:

```python
@agent.step(name="guardian_validate")
async def guardian_validate(query, context_id):
    """Call Guardian via A2A to validate the request."""
    guardian_card = await tool_find_agent.ainvoke("guardian")
    # Sends validation request via AgentInteractionFlow
    # Returns: {"status": "approved|blocked", "allowed": True|False, "reason": "..."}
```

If Guardian says blocked, the Orchestrator stops immediately and returns the reason to the user.

## Check Guardian status

```bash
curl http://localhost:11438/health
curl http://localhost:11438/v1/tools/get_guardian_status
curl http://localhost:11438/v1/tools/get_security_metrics
```

## Next step

👉 [OPA Policies](02-opa-policies.md)
