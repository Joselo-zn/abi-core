# Guardian Service

Guardian is the security service that protects your agent system.

## What Guardian Does

- 🔒 Access control
- 📝 Action auditing
- ⚠️ Security alerts
- 📊 Monitoring dashboard

## Add Guardian

```bash
abi-core create project my-app --with-guardian
```

Or add to existing project:
```bash
abi-core add service guardian-native
```

## Components

### 1. Guardian Agent
Monitors and applies policies.

### 2. OPA (Open Policy Agent)
Policy evaluation engine.

### 3. Dashboard
Web interface for monitoring.

## Access Dashboard

```
http://localhost:8080
```

## Next Steps

- [OPA policies](02-opa-policies.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
