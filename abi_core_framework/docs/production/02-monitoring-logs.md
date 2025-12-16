# Monitoring and Logs

Monitor your agent system in production.

## View Logs

### All services
```bash
docker-compose logs -f
```

### Specific service
```bash
docker-compose logs -f my-agent-agent
```

### Last N lines
```bash
docker-compose logs --tail=100 my-agent-agent
```

## Service Status

```bash
# View status
docker-compose ps

# View resources
docker stats
```

## Metrics

### Guardian Dashboard
```
http://localhost:8080
```

Shows:
- Active agents
- Requests per second
- Errors
- Latency

## Alerts

Configure alerts in `services/guardian/alerting_config.json`:

```json
{
  "alerts": [
    {
      "name": "high_error_rate",
      "condition": "error_rate > 0.1",
      "action": "send_email"
    }
  ]
}
```

## Next Steps

- [Troubleshooting](03-troubleshooting.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
