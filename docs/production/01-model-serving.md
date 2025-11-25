# Model Serving

ABI-Core supports two model serving strategies.

## Centralized (Recommended for Production)

One Ollama serves all agents:

```bash
abi-core create project my-app --model-serving centralized
```

**Advantages**:
- ✅ Less resources
- ✅ Centralized management
- ✅ Faster startup

**Architecture**:
```
Central Ollama
  ↑
  ├─ Agent 1
  ├─ Agent 2
  └─ Agent 3
```

## Distributed (Development)

Each agent has its own Ollama:

```bash
abi-core create project my-app --model-serving distributed
```

**Advantages**:
- ✅ Complete isolation
- ✅ Independent versions

**Architecture**:
```
Agent 1 ← Ollama 1
Agent 2 ← Ollama 2
Agent 3 ← Ollama 3
```

## Change Strategy

Edit `.abi/runtime.yaml`:

```yaml
project:
  model_serving: centralized  # or distributed
```

## Next Steps

- [Monitoring and logs](02-monitoring-logs.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
