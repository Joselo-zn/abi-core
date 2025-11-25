# Probar y Depurar Agentes

Aprende a probar y depurar tus agentes de forma efectiva.

## Pruebas Básicas

### Con curl
```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "context_id": "test", "task_id": "1"}'
```

### Con Python
```python
import requests

def test_agent(query):
    response = requests.post(
        "http://localhost:8000/stream",
        json={"query": query, "context_id": "test", "task_id": "1"}
    )
    assert response.status_code == 200
    assert 'content' in response.json()
    print(f"✅ Test passed: {query}")

test_agent("Hola")
test_agent("¿Qué es Python?")
```

## Ver Logs

```bash
# Logs en tiempo real
docker-compose logs -f mi-agente-agent

# Últimas 100 líneas
docker-compose logs --tail=100 mi-agente-agent
```

## Depuración

### Agregar Logs
```python
from abi_core.common.utils import abi_logging

def process(self, enriched_input):
    abi_logging(f"INPUT: {enriched_input}")
    # ... tu código
    abi_logging(f"OUTPUT: {result}")
    return result
```

### Probar Localmente
```python
# test_local.py
from agents.mi_agente.agent_mi_agente import MiAgente
import os

os.environ['MODEL_NAME'] = 'qwen2.5:3b'
os.environ['OLLAMA_HOST'] = 'http://localhost:11434'

agent = MiAgente()
result = agent.handle_input("test")
print(result)
```

## Próximos Pasos

- [Múltiples agentes](../multi-agent-basics/01-why-multiple-agents.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
