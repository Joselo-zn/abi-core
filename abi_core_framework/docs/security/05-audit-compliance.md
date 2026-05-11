# Audit & Compliance

Every security decision is logged. You can trace who did what, when, and why it was allowed or denied.

## What gets logged

Every A2A call and MCP tool access produces an audit event:

```json
{
  "event_type": "a2a_access",
  "timestamp": "2026-05-11T10:30:00Z",
  "source_agent": "orchestrator",
  "target_agent": "planner",
  "allowed": true,
  "reason": null,
  "risk_score": 0.15
}
```

## Where logs go

- **Container logs** — `docker compose logs guardian`
- **Emergency logs** — `services/guardian/emergency_logs/` (for blocked high-risk events)
- **Artifact Store** — If `LOG_TO_ARTIFACT_STORE=true`, logs go to MinIO for long-term storage

## View logs

```bash
# Real-time Guardian logs
docker compose logs -f <project>-guardian

# Security metrics
curl http://localhost:11438/v1/tools/get_security_metrics

# Guardian status
curl http://localhost:11438/v1/tools/get_guardian_status
```

## Log format in container output

```
✅ Semantic access granted for 'agent://planner' | user: admin@co.com (risk: 0.15)
❌ Semantic access denied for 'agent://unknown' | reason: Agent not registered (risk: 0.90)
[📋 AUDIT] a2a_access: orchestrator → planner | allowed=True
```

## Risk scoring

Guardian assigns a risk score (0.0 to 1.0) based on:
- Agent trust level (registered vs unknown)
- Request patterns (frequency, time of day)
- Action sensitivity
- Policy evaluation results

If risk exceeds `MAX_RISK_THRESHOLD` (default 0.7), the request is blocked regardless of other rules.

## Next step

👉 [A2A Validation](06-a2a-validation.md)
