# 🗺️ **ABI Roadmap – 2025**

> **🎉 HITO ALCANZADO:** Sistema **ABI-Core completamente operativo (Octubre 2025)**  
> Todos los servicios funcionando, errores críticos resueltos, arquitectura estable y modular.

* * *

## ✅ **Completado (Julio – Octubre 2025)**

*(Se conserva íntegramente la sección original del historial de logros y baseline técnico.)*

* * *

## 🟡 **En Progreso / Próximos Hitos (Octubre – Noviembre 2025)**

> **Objetivo general del ciclo:**  
> Refactorizar el *Orchestrator Core* con **LangGraph**, implementar colas distribuidas (**Redis/Rabbit**), añadir **seguridad con OpenBao**, y preparar el lanzamiento de **ABI-Core como paquete PyPI** con CLI oficial.

| Prioridad | Tarea | Timeline | Responsable | Objetivo |
| --- | --- | --- | --- | --- |
| **P0** | **Refactor Orchestrator con LangGraph (Core Flux)** | 2 semanas | José Luis | Migrar el flujo actual a LangGraph para habilitar nodos pausable/resumibles (`input-required`) y control de estado en tiempo real. |
| **P0** | **Integración Redis/Rabbit como columna vertebral** | 1 semana | José Luis | Establecer colas para requests, deduplicación (`idemp_key`) y manejo concurrente de tareas entre agentes. |
| **P0** | **Implementar modelo TurnState + Resume System** | 4 días | José Luis | Habilitar persistencia de turnos y reanudación de flujos (pausable graph execution). |
| **P1** | **Ruteo automático `input-required`** | 3 días | José Luis | Crear heurística para decidir si responde el Orchestrator, espera al usuario o reenvía al Planner/Worker. |
| **P1** | **Vault seguro con OpenBao (AgentCards)** | 1 semana | José Luis | Centralizar secretos y credenciales de agentes con versionamiento seguro. |
| **P1** | **CLI de pruebas (`abi run`, `resume`, `logs`)** | 1 semana | José Luis | Ejecutar flujos, reanudar tareas y ver logs locales fácilmente. |
| **P2** | **Integrar OpenTelemetry (MVP)** | 1 semana | José Luis | Exportar métricas de latencia, duplicación y estados de flujo a Grafana/Tempo. |
| **P2** | **Mejora de prompts QA/Planner** | 3 días | José Luis | Asegurar determinismo, limpieza de contexto y salida estructurada. |
| **P2** | **Documentación técnica completa (`docs/`)** | 2 semanas | José Luis | Incluir arquitectura LangGraph, colas, ruteo y CLI en el sitio técnico. |
| **P3** | **Video demo y contenido de lanzamiento** | 3 semanas | José Luis | Mostrar orquestación LangGraph + Redis + Observer Agent en acción. |