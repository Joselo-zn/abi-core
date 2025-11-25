# Síntesis de Resultados

El Orchestrator combina resultados de múltiples agentes en una respuesta coherente.

## Cómo Funciona

1. Agentes ejecutan sus tareas
2. Cada agente retorna un resultado
3. Orchestrator usa LLM para sintetizar
4. Usuario recibe respuesta unificada

## Ejemplo

```
Agente 1: "Ventas: $100,000"
Agente 2: "Crecimiento: 15%"
Agente 3: "Top producto: Widget A"

Síntesis:
"Las ventas alcanzaron $100,000 con un crecimiento del 15%.
El producto más vendido fue Widget A."
```

## Próximos Pasos

- [RAG y Conocimiento](../rag/01-what-is-rag.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
