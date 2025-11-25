# Model Serving

ABI-Core soporta dos estrategias de servicio de modelos.

## Centralizado (Recomendado para Producción)

Un solo Ollama sirve a todos los agentes:

```bash
abi-core create project mi-app --model-serving centralized
```

**Ventajas**:
- ✅ Menos recursos
- ✅ Gestión centralizada
- ✅ Inicio más rápido

**Arquitectura**:
```
Ollama Central
  ↑
  ├─ Agente 1
  ├─ Agente 2
  └─ Agente 3
```

## Distribuido (Desarrollo)

Cada agente tiene su propio Ollama:

```bash
abi-core create project mi-app --model-serving distributed
```

**Ventajas**:
- ✅ Aislamiento completo
- ✅ Versiones independientes

**Arquitectura**:
```
Agente 1 ← Ollama 1
Agente 2 ← Ollama 2
Agente 3 ← Ollama 3
```

## Cambiar Estrategia

Edita `.abi/runtime.yaml`:

```yaml
project:
  model_serving: centralized  # o distributed
```

## Próximos Pasos

- [Monitoreo y logs](02-monitoring-logs.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
