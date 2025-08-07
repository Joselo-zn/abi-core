# 🚀 ABI - MVP Local

El MVP corre localmente usando `docker-compose.mvp.yml`.

---

## 🧩 Componentes mínimos

- ✅ **Orchestrator**
- ✅ **2 Workers** (observe + act)
- ✅ **Verifier**
- ✅ **Auditor**
- ✅ **Ollama** con **LLaMA 3.1:405b**
- ✅ **MCP Client** + **MCP Toolbox**
- ✅ **Frontend básico**
- ✅ **Redis** y **TinyDB**
- ✅ Memoria semántica local (**Weaviate** opcional)

---

## 📁 Diagrama de carpetas

abi-core/
├── agents/
│ ├── base/
│ ├── orchestrator/
│ ├── worker-observe/
│ ├── worker-act/
│ ├── verifier/
│ └── auditor/
├── mcp/
│ ├── client/
│ └── toolbox/
├── memory/
│ ├── redis/
│ ├── tinydb/
│ └── weaviate/ # Opcional
├── frontend/
│ └── dashboard/
├── docker/
│ ├── Dockerfile.agent
│ ├── Dockerfile.ollama
│ └── docker-compose.mvp.yml
├── notebooks/
│ └── tests/
├── README.md
└── ROADMAP.md


flowchart TD

%% ─────── Layer 1: Human Interaction ───────
subgraph L1["UI"]
    UI["Simple Frontend (Vue.js)"]
end

%% ─────── Layer 2: Orchestration ───────
subgraph L2["Orchestration"]
    ORCH["Orchestrator Agent"]
end

%% ─────── Layer 3: Execution ───────
subgraph L3["Execution"]
    WORK["Worker Agent"]
end

%% ─────── Layer 4: Discovery / Context ───────
subgraph L4["Context & Discovery"]
    MCP["MCP Server"]
end

%% ─────── Layer 5: LLM & Memory ───────
subgraph L5["LLM & Memory"]
    OLLAMA["Ollama"]
    MODEL["LLaMA 3.1:405B"]
    REDIS["Redis"]
    VDB["Weaviate (opcional)"]
end

%% ─────── Layer 6: Agent Base ───────
subgraph L6["Shared Logic"]
    BASE["BaseAgent"]
end

%% Connections
UI --> ORCH
ORCH --> WORK & MCP
WORK --> OLLAMA & REDIS
OLLAMA --> MODEL
ORCH & WORK --> BASE
WORK --> VDB

%% Styling
classDef agent fill:#f9f,stroke:#333,stroke-width:2px
class ORCH,WORK agent
