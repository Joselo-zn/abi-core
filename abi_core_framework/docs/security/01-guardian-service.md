# Guardian Service

Guardian is the security gate. Every request can be checked against your rules before it runs.

## What it does

- Checks if a request is allowed before executing it
- Evaluates security rules (allow, deny, or require approval)
- Logs all decisions for auditing

## Components

| Service | Port | Role |
|---------|------|------|
| Guardian Agent | 11438 | Receives validation requests, calls OPA, returns decisions |
| OPA | 8181 | Evaluates Rego policies, returns allow/deny |

```{note}
Older scaffolding still maps a `dashboard_port` (8080) for Guardian in
`compose.yaml`, and an earlier Guardian implementation (`agent_deprecated/`
in the scaffolding templates: `dashboard.py.j2`, `metrics_collector.py.j2`,
`alerting_system.py.j2`) shipped a web dashboard and `/metrics` endpoint. The
current Guardian (`abi-core add service guardian-native`, the AbiCore-based
`agent/` implementation) does not serve a dashboard — it's a plain
`parse_request → evaluate_policy → format_decision` DAG behind the standard
A2A endpoints (below). Don't rely on port 8080 for it.
```

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
    guardian_card = await find_infra_agent("guardian")
    # find_infra_agent (not tool_find_agent) — guarantees a stale ephemeral
    # agent card can never be returned in Guardian's place.
    # Sends validation request via AgentInteractionFlow
    # Returns: {"status": "approved|blocked", "allowed": True|False, "reason": "..."}
```

If Guardian says blocked, the Orchestrator stops immediately and returns the reason to the user.

## Check Guardian status

Guardian is a standard AbiCore/A2A agent, so it exposes the same generic
endpoints every ABI agent does — there is no `/v1/tools/...` REST interface:

```bash
curl http://localhost:11438/health   # liveness only: {"ok": true}
curl http://localhost:11438/card     # this agent's AgentCard (JSON)
```

`/health` is a plain liveness check, not a rich security report — Guardian's
own `health_check()` (OPA connectivity, core-policy presence,
`SECURE_AND_OPERATIONAL` vs `SECURITY_ISSUES_DETECTED`) runs at startup
(`initialize_security()`, which blocks the process from starting if it
fails) but isn't currently wired to a public endpoint. To validate an action
directly, send it as a normal A2A/task request to Guardian (JSON body with
`action`, `resource_type`, `source_agent`, ...) rather than via a REST tool
route.

## Next step

👉 [OPA Policies](02-opa-policies.md)
