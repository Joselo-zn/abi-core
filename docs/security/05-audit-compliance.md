# Audit and Compliance

Guardian logs all actions for auditing and regulatory compliance.

## Audit Logs

Guardian records:
- Who did what
- When they did it
- Action result
- Policies evaluated

## View Logs

```bash
docker-compose logs guardian
```

## Audit Dashboard

Access the dashboard:
```
http://localhost:8080/audit
```

You'll see:
- Action history
- Violated policies
- Security alerts
- Compliance metrics

## Export Logs

```bash
# Export logs to file
docker-compose logs guardian > audit.log
```

## Next Steps

- [Model serving](../production/01-model-serving.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
