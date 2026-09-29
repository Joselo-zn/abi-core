# Audit & Compliance

Every security decision is logged. You can trace who did what, when, and why it was allowed or denied.

## What gets logged

Every A2A call and MCP tool access produces an audit event.

A2A call (`abi_core.security.a2a_access_validator`, POSTed to the target
agent's `/audit/log`):

```json
{
  "event_type": "a2a_access",
  "timestamp": "2026-05-11T10:30:00Z",
  "source_agent": "orchestrator",
  "target_agent": "planner",
  "allowed": true,
  "reason": null,
  "context": { "...": "full OPA input, see A2A Validation" }
}
```

Semantic Layer / MCP tool access (`abi_core.semantic.semantic_access_validator`,
see [A2A Validation → Semantic Layer access
validation](06-a2a-validation.md#semantic-layer-mcp-access-validation))
additionally carries a `risk_score` (0.0–1.0), since OPA's
`abi.semantic_access` policy computes one — the `a2a_access` policy doesn't.

## Where logs go

- **Container logs** — `docker compose logs guardian` (validators log
  grant/deny decisions via `abi_logging`; the audit-log route logs every
  received A2A audit event)
- **Artifact Store** — If `LOG_TO_ARTIFACT_STORE=true`, logs go to MinIO for long-term storage

```{note}
`services/guardian/emergency_logs/` and Guardian's `emergency_shutdown()`
persisting anything to it are part of an earlier Guardian implementation
(`agent_deprecated/emergency_response.py.j2` in the scaffolding). The
current `AbiGuardianAgent.emergency_shutdown()` flips an in-memory flag
(blocks all further requests) and returns a result dict — it doesn't write
to that directory.
```

## View logs

```bash
# Real-time Guardian logs
docker compose logs -f <project>-guardian

# Guardian liveness
curl http://localhost:11438/health
```

There's no `/v1/tools/get_security_metrics` or `/v1/tools/get_guardian_status`
REST endpoint in the current Guardian — see [Guardian Service → Check
Guardian status](01-guardian-service.md) for what's actually exposed.
Security/access-decision logs themselves come from the validators
(`semantic_access_validator`, `a2a_access_validator`) and Guardian's own
`abi_logging` output, visible via `docker compose logs`.

## Log format in container output

```
✅ Semantic access granted for 'agent://planner' | user: admin@co.com (risk: 0.15)
❌ Semantic access denied for 'agent://unknown': Agent not registered (risk: 0.90)
[📋 AUDIT] a2a_access: orchestrator → planner | allowed=True |
```

## Risk scoring

Two separate mechanisms compute a risk score — don't conflate them:

**Semantic Layer access** (`abi.semantic_access` policy,
`semantic_access.rego`) — the `risk_score` you see in the "Semantic access
granted/denied" log lines above. It's a sum of modifiers, capped at 1.0:
- Base risk by action (e.g. `find_agent` 0.1, `register_agent` 0.6,
  `unregister_agent` 0.8)
- MCP tool risk (e.g. `echo_tool` 0.0, `delete_tool` 0.4, unknown tool 0.2)
- Source IP risk (+0.2 unknown IP, +0.1 non-internal IP)
- Time-of-day risk (+0.1 between 22:00–06:00)
- Agent trust risk (0.0 trusted, +0.15 ephemeral, +0.1/+0.2 for
  medium/low `trust_level` on untrusted agents)

**Guardian's own action/workflow validation** (`evaluate_policy` step,
`policy_engine_secure`) — the score is `max(core_risk, custom_risk)`, the
higher of Guardian's immutable core policies and your custom policy's own
`risk_score` output. For workflow validation (`validate_workflow`, multiple
actions in one call), an action above `HIGH_RISK_THRESHOLD` (env var,
default `0.7`) is flagged `high_risk`, and the workflow as a whole is only
allowed if nothing was denied *and* the average risk across all actions
stays under that same threshold — a single denied action always blocks the
workflow regardless of its own risk score.

## Next step

👉 [A2A Validation](06-a2a-validation.md)
