# 🚀 ABI - MVP Operativo

El MVP está completamente funcional usando `docker-compose.yml`.

---

## 🧩 Componentes Implementados

- ✅ **Orchestrator Agent** - Coordinación de workflows (Puerto 8082)
- ✅ **Planner Agent** - Planificación de tareas (Puerto 11437)
- ✅ **Actor Agent** - Ejecución de acciones (Puerto 8083)
- ✅ **Guardian Agent** - Seguridad y políticas (Puerto 11438)
- ✅ **Observer Agent** - Monitoreo (En desarrollo)
- ✅ **Semantic Layer** - MCP Server con embeddings (Puerto 10100)
- ✅ **Ollama LLM Base** - Modelos locales (Puerto 11434)
- ✅ **Weaviate** - Base de datos vectorial (Puerto 8080)
- ✅ **OPA** - Motor de políticas (Puerto 8181)
- ✅ **A2A Protocol** - Comunicación inter-agentes
- ✅ **Health Monitoring** - Endpoints de salud

---

## 📁 Estructura Actual del Sistema

```
abi-core/
├── agents/
│   ├── abi-llm-base/           # Base común para todos los agentes
│   │   ├── agent/              # Lógica base de agentes
│   │   ├── common/             # A2A server, executor, workflow
│   │   ├── opa/                # Políticas base
│   │   ├── mcp/                # Cliente MCP
│   │   └── agent_cards/        # Definiciones de agentes
│   ├── orchestrator/           # Coordinador principal
│   ├── planner/                # Planificador de tareas
│   ├── worker_actor/           # Ejecutor de acciones
│   ├── guardial/               # Agente de seguridad
│   │   ├── agent/              # Lógica del guardian
│   │   └── opa/                # Servidor OPA dedicado
│   └── worker-observer/        # Observador (futuro)
├── semantic_layer/             # Capa semántica
│   └── layer/
│       ├── mcp_server/         # Servidor MCP
│       └── embedding_mesh/     # Embeddings y Weaviate
├── testing/                    # Suite de pruebas
└── docker-compose.yml         # Orquestación completa
```


## 🏗️ Arquitectura del Sistema Actual

```mermaid
flowchart TD
    %% ─────── Layer 1: Entry Points ───────
    subgraph L1["🌐 Entry Points"]
        API["API Gateway<br/>(Futuro)"]
        A2A["A2A Protocol<br/>:8082"]
    end

    %% ─────── Layer 2: Orchestration ───────
    subgraph L2["🎯 Orchestration Layer"]
        ORCH["Orchestrator Agent<br/>:8082"]
        GUARD["Guardian Agent<br/>:11438"]
    end

    %% ─────── Layer 3: Planning & Execution ───────
    subgraph L3["⚡ Execution Layer"]
        PLAN["Planner Agent<br/>:11437"]
        ACTOR["Actor Agent<br/>:8083"]
        OBS["Observer Agent<br/>(Futuro)"]
    end

    %% ─────── Layer 4: Semantic & Discovery ───────
    subgraph L4["🧠 Semantic Layer"]
        MCP["MCP Server<br/>:10100"]
        EMBED["Embedding Mesh"]
    end

    %% ─────── Layer 5: Infrastructure ───────
    subgraph L5["🔧 Infrastructure"]
        OLLAMA["Ollama LLM<br/>:11434"]
        WEAV["Weaviate DB<br/>:8080"]
        OPA["OPA Engine<br/>:8181"]
    end

    %% ─────── Layer 6: Base Components ───────
    subgraph L6["📦 Shared Components"]
        BASE["ABI-LLM-Base"]
        A2ASERV["A2A Server"]
        WORKFLOW["Workflow Engine"]
    end

    %% Connections - Entry
    API -.-> ORCH
    A2A --> ORCH

    %% Connections - Orchestration
    ORCH --> PLAN
    ORCH --> ACTOR
    GUARD --> ORCH
    GUARD --> PLAN
    GUARD --> ACTOR

    %% Connections - Execution
    PLAN --> ACTOR
    ACTOR --> OBS
    
    %% Connections - Semantic
    ORCH --> MCP
    PLAN --> MCP
    ACTOR --> MCP
    MCP --> EMBED
    EMBED --> WEAV

    %% Connections - Infrastructure
    ORCH --> OLLAMA
    PLAN --> OLLAMA
    ACTOR --> OLLAMA
    GUARD --> OPA
    
    %% Connections - Base
    ORCH --> BASE
    PLAN --> BASE
    ACTOR --> BASE
    GUARD --> BASE
    BASE --> A2ASERV
    BASE --> WORKFLOW

    %% Styling
    classDef agent fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef infra fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef semantic fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef security fill:#ffebee,stroke:#b71c1c,stroke-width:2px
    classDef future fill:#f5f5f5,stroke:#757575,stroke-width:1px,stroke-dasharray: 5 5

    class ORCH,PLAN,ACTOR agent
    class OLLAMA,WEAV,OPA infra
    class MCP,EMBED semantic
    class GUARD security
    class API,OBS future
```

## 🔄 Flujo de Trabajo Actual

1. **Request A2A** → Orchestrator (:8082)
2. **Guardian** valida políticas y seguridad
3. **Orchestrator** consulta **MCP Server** para discovery
4. **Planner** descompone la tarea en subtareas
5. **Actor** ejecuta las acciones específicas
6. **Guardian** monitorea y audita cada paso
7. **Weaviate** proporciona contexto semántico
8. **OPA** valida políticas en tiempo real

## 🚀 Estado del MVP

- ✅ **Sistema Completamente Operativo**
- ✅ **Todos los Servicios Funcionando**
- ✅ **Health Checks Pasando**
- ✅ **Comunicación A2A Establecida**
- ✅ **Seguridad y Políticas Activas**
- ⏳ **Entry Point HTTP Simple** (Próxima implementación)

## 🌐 Endpoints y Puertos

### Servicios Principales
| Servicio | Puerto | Endpoint | Estado |
|----------|--------|----------|--------|
| **Orchestrator** | 8082 | `POST /` (A2A) | ✅ Activo |
| **Guardian** | 11438 | `GET /health` | ✅ Activo |
| **Planner** | 11437 | A2A Protocol | ✅ Activo |
| **Actor** | 8083 | `GET /health` | ✅ Activo |
| **Semantic Layer** | 10100 | `GET /health` | ✅ Activo |

### Infraestructura
| Servicio | Puerto | Endpoint | Estado |
|----------|--------|----------|--------|
| **Ollama LLM** | 11434 | `/api/tags` | ✅ Activo |
| **Weaviate** | 8080 | `/v1/.well-known/ready` | ✅ Activo |
| **OPA Engine** | 8181 | `/health` | ✅ Activo |

### Health Check Rápido
```bash
# Verificar todos los servicios
curl -s http://localhost:8181/health    # OPA
curl -s http://localhost:8080/v1/.well-known/ready  # Weaviate  
curl -s http://localhost:10100/health   # Semantic Layer
curl -s http://localhost:11438/health   # Guardian
curl -s http://localhost:8082/health    # Orchestrator
curl -s http://localhost:8083/health    # Actor
```

## 🔧 Comandos de Desarrollo

### Iniciar el Sistema
```bash
cd abi-core
docker-compose up -d
```

### Verificar Estado
```bash
docker-compose ps
docker-compose logs abi-guardial
```

### Parar el Sistema
```bash
docker-compose down
```

## 📋 Próximos Pasos

1. **Entry Point HTTP** - Implementar endpoint `/stream` simple
2. **Observer Agent** - Activar agente de monitoreo
3. **API Gateway** - Crear interfaz REST amigable
4. **Dashboard Web** - Interfaz de usuario
5. **PyPI Package** - Distribución como `abi-core`

---

*Última actualización: 7 de Octubre, 2025*  
*Sistema MVP completamente operativo* ✅