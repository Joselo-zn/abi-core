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
Guardian listens on port 11438 inside its container, and the scaffolding maps it to the same port on the host. Projects created with abi-core-ai 1.13.74 or earlier map `11438:11434` instead, so `localhost:11438` doesn't reach Guardian from the host. In such a project, change that line in `compose.yaml` to `"11438:11438"` — or check Guardian from inside its container with `docker compose exec <project>-guardian wget -qO- http://localhost:11438/health`.
```

## Add Guardian to your project

```bash
abi-core create project --name my-app --with-guardian
```

The Guardian is created with the project only; `abi-core add service` has no Guardian type.

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
curl http://localhost:11438/health                         # liveness only
curl http://localhost:11438/.well-known/agent-card.json     # this agent's AgentCard (JSON)
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
