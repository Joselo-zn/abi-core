# ABI-Core Architecture

Overview of the system architecture.

## System Layers

```
┌─────────────────────────────────────────┐
│         User Application                │
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

## Main Components

### 1. Agents
AI programs that execute specific tasks.

### 2. Semantic Layer
Agent discovery and routing.

### 3. Orchestration Layer
Multi-agent workflow coordination.

### 4. Security Layer
Policies and auditing.

## Data Flow

```
User → Orchestrator → Planner → Semantic Layer
                                         ↓
                                   Find Agents
                                         ↓
                                   Execute Workflow
                                         ↓
                                   Synthesize Results
                                         ↓
                                      User
```

## Communication

### A2A Protocol
Agent-to-agent communication.

### MCP Protocol
Communication with semantic layer.

### REST API
Communication with users.

## Storage

### Weaviate
Vector database for embeddings.

### Ollama
LLM model storage.

### Logs
Log files for auditing.

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
