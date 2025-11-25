# Tu Primer Sistema Multi-Agente

Crea un sistema completo con múltiples agentes trabajando juntos.

## Lo Que Vas a Construir

Un sistema de análisis con 3 agentes:
1. **Recolector**: Obtiene datos
2. **Analista**: Analiza datos
3. **Reportero**: Genera reportes

## Paso 1: Crear el Proyecto

```bash
abi-core create project sistema-analisis --with-semantic-layer
cd sistema-analisis
abi-core provision-models
```

## Paso 2: Crear los Agentes

```bash
# Agente 1: Recolector
abi-core add agent recolector \
  --description "Recolecta datos de fuentes"

# Agente 2: Analista
abi-core add agent analista \
  --description "Analiza datos recolectados"

# Agente 3: Reportero
abi-core add agent reportero \
  --description "Genera reportes"
```

## Paso 3: Crear Agent Cards

```bash
abi-core add agent-card recolector \
  --url "http://recolector-agent:8000" \
  --tasks "recolectar_datos,obtener_fuentes"

abi-core add agent-card analista \
  --url "http://analista-agent:8001" \
  --tasks "analizar_datos,calcular_metricas"

abi-core add agent-card reportero \
  --url "http://reportero-agent:8002" \
  --tasks "generar_reporte,formatear_datos"
```

## Paso 4: Iniciar el Sistema

```bash
docker-compose up -d
```

## Paso 5: Probar el Sistema

```python
import requests

# Llamar al recolector
datos = requests.post(
    "http://localhost:8000/stream",
    json={"query": "Recolecta datos de ventas", "context_id": "test", "task_id": "1"}
).json()

# Llamar al analista
analisis = requests.post(
    "http://localhost:8001/stream",
    json={"query": f"Analiza: {datos['content']}", "context_id": "test", "task_id": "2"}
).json()

# Llamar al reportero
reporte = requests.post(
    "http://localhost:8002/stream",
    json={"query": f"Genera reporte de: {analisis['content']}", "context_id": "test", "task_id": "3"}
).json()

print(reporte['content'])
```

## Próximos Pasos

- [Capa semántica](../semantic-layer/01-what-is-semantic-layer.md)
- [Orquestación avanzada](../orchestration/01-planner-orchestrator.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
