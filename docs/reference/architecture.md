# Arquitectura de ABI-Core

Visión general de la arquitectura del sistema.

## Capas del Sistema

```
┌─────────────────────────────────────────┐
│         Aplicación del Usuario          │
│        (Web, CLI, API, etc.)            │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│          Orchestration Layer            │
│  ┌──────────┐        ┌──────────┐      │
│  │ Planner  │───────→│Orchestr. │      │
│  └──────────┘        └──────────┘      │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│            Agent Layer                  │
│  ┌────────┐ ┌────────┐ ┌────────┐     │
│  │Agent 1 │ │Agent 2 │ │Agent 3 │     │
│  └────────┘ └────────┘ └────────┘     │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│         Semantic Layer                  │
│  ┌──────────┐      ┌──────────┐        │
│  │   MCP    │──────│ Weaviate │        │
│  │  Server  │      │ (Vector) │        │
│  └──────────┘      └──────────┘        │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│         Security Layer                  │
│  ┌──────────┐      ┌──────────┐        │
│  │ Guardian │──────│   OPA    │        │
│  └──────────┘      └──────────┘        │
└─────────────────────────────────────────┘
```

## Componentes Principales

### 1. Agentes
Programas de IA que ejecutan tareas específicas.

### 2. Semantic Layer
Descubrimiento y routing de agentes.

### 3. Orchestration Layer
Coordinación de workflows multi-agente.

### 4. Security Layer
Políticas y auditoría.

## Flujo de Datos

```
Usuario → Orchestrator → Planner → Semantic Layer
                                         ↓
                                   Encuentra Agentes
                                         ↓
                                   Ejecuta Workflow
                                         ↓
                                   Sintetiza Resultados
                                         ↓
                                      Usuario
```

## Comunicación

### A2A Protocol
Comunicación entre agentes.

### MCP Protocol
Comunicación con capa semántica.

### REST API
Comunicación con usuarios.

## Almacenamiento

### Weaviate
Base de datos vectorial para embeddings.

### Ollama
Almacenamiento de modelos LLM.

### Logs
Archivos de log para auditoría.

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
