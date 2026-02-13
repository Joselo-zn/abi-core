# 📦 abi-core/

**Objetivo:** Construcción lógica del sistema ABI (agentes, modelos, semántica, UI, interacción).

---

## 🧠 Agentes & Lógica Cognitiva

- **Python (3.10+)**
- **FastAPI** – para exponer endpoints de cada agente
- **LangChain / Haystack** – para wrappers de LLMs o herramientas
- **MCP Client** – ejecución local de tareas con agentes
- **MCP Toolbox** – flujos A2A, validación, razonamiento compartido

---

## 🤖 Modelos de lenguaje

- **Ollama** – ejecución local de modelos LLM
- **LLaMA 3.1:405B** – modelo opensource descargado

---

## 📚 Semántica y contexto compartido

- **A2A Protocol** (propio, usando JSON-LD, RDF, OWL)
- **YAML / JSON Schema** – definición de configuraciones y reglas
- **Markdown + Mermaid.js** – documentación viva y diagramas

---

## 🧠 Memoria y persistencia local

- **Redis** – caché semántica / comunicación entre agentes
- **TinyDB / SQLite** – almacenamiento local de estados
- **Weaviate / ChromaDB** – vectores de memoria semántica *(opcional MVP)*

---

## 🖥 Interfaz & interacción humana

- **Vue.js / Next.js** – frontend del panel de supervisión
- **ShadCN / TailwindCSS** – UI moderna
- **Socket.IO / WebRTC** – interacción en tiempo real

---

## 🛠️ Desarrollo & testing

- **Docker** – contenedores por agente
- **Docker Compose** – levantar el entorno MVP local
- **VS Code DevContainers** – entorno reproducible
- **Jupyter Notebooks** – pruebas interactivas
- **Webhook Relay / ngrok** – pruebas de conectividad remota


abi-core/
├── agents/
│   ├── orchestrator/
│   ├── worker-observe/
│   ├── worker-act/
│   ├── verifier/
│   ├── auditor/
│   └── factory/
├── models/
│   ├── llama3.1-405b/
│   └── ollama-config/
├── mcp/
│   ├── client/
│   └── toolbox/
├── semantic/
│   ├── a2a/
│   ├── schemas/
│   ├── memory/
│   └── rules/
├── persistence/
│   ├── redis/
│   ├── weaviate/
│   └── tinydb/
├── frontend/
│   └── dashboard/
├── docker/
│   ├── Dockerfile.agent
│   ├── Dockerfile.ollama
│   └── entrypoints/
├── compose/
│   └── docker-compose.mvp.yml
├── ROADMAP.md
├── architecture.md
├── governance.md
├── agent_protocols.md
└── README.md
