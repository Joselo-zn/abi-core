# ✅ `stack.md` (ENGLISH VERSION)

---

## 🧱 Physical Infrastructure & Orchestration

- **Kubernetes (K3s / GKE / EKS)** – container orchestration and logical separation of agents, using `StatefulSet` for agents requiring persistence.
- **Helm** – deployment packaging for reproducible rollouts of agents and services.
- **Terraform** – infrastructure as code provisioning.
- **Ansible** – automated setup of dependencies, environments, and clusters.
- **Prometheus + Grafana** – monitoring and real-time metrics visualization.
- **Vault / Sealed Secrets** – encrypted and secure secrets management.

---

## 🧠 Cognitive Layer (Intelligent Agents)

- **Python (FastAPI + LangChain)** – modular agent development framework.
- **BaseAgent** – shared base class defining structure and behaviors of all ABI agents.
- **Ollama** – local LLM runtime with shared download volume across pods.
- **LLMs** – LLaMA 3.1, Claude, GPT-4o, Mistral – connectable via Ollama or remote adapters.
- **MCP Client** – interface for agents to interact with the MCP ecosystem.
- **MCP Toolbox** – tools for validation, shared context, and A2A-based reasoning.
- **Redis** – agent state/event synchronization layer.
- **Weaviate / ChromaDB** – distributed semantic vector memory store.
- **TinyDB / SQLite** – lightweight local state persistence per agent.

---

## 🧬 Semantic & Context Layer

- **Model Context Protocol (MCP)** – shared context, memory, and distributed reasoning coordination.
- **A2A (Agent-to-Agent Protocol)** – semantic interaction protocol using RDF/OWL and JSON-LD.
- **YAML / JSON Schemas** – declarative configuration of rules, policies, and agent capabilities.
- **Neo4j (optional)** – in-memory semantic graph database for distributed inference and shared context.

### 🔹 As a Semantic Repository

- Tracks who said what, when, in what context, and with what outcome.
- Models concepts (tasks, agents, decisions) as nodes and relations as edges.

### 🔹 As a Reasoning Engine

- Agents can query past relations and events.
- Supports inference patterns like propagation, relevance scoring, belief tracking.
- RDF/OWL-compatible via translation layer.

---

## 🛡️ Security & Governance

- **Keycloak** – identity and access management (SSO, LDAP, OAuth2).
- **OPA (Open Policy Agent)** – policy enforcement and access validation for agents.
- **Immutable Logs (Loki / Wazuh / Sigstore)** – full traceability and action audit logs.
- **Airgap Agents / Firecracker** *(optional)* – hardened isolation for critical agents.

---

## 🧰 Development & Supervision Tools

- **VS Code + DevContainers** – reproducible portable development environments.
- **Jupyter Notebooks + LangChain** – interactive agent experimentation and testing.
- **N8N / Temporal.io** – asynchronous workflows and task orchestration across agents.
- **Webhook Relay / ngrok** – controlled remote testing from outside the cluster.

---

## 🌍 Human Interface & Collaboration

- **Vue.js / Next.js** – dashboards for human interaction and system supervision.
- **Socket.IO / WebRTC** – real-time interaction channels with agents.
- **Markdown + Mermaid.js** – living documentation, architecture diagrams, and traceable state.

---

## 📦 Distribution & Installation

- **Helm** – primary packaging tool per agent or module.
- **GitHub Actions / Woodpecker CI** – local or cloud-based CI/CD pipelines.
- **Inno Setup / NSIS / Snapcraft / Homebrew** *(optional)* – native installable package creation.

---

## 🧭 Optional / Advanced

- **NeMo / HuggingFace Transformers** – fine-tuning and custom model training.
- **AgentVerse / Autogen / CrewAI** – multi-agent architecture experimentation.
- **DeltaLake / DuckDB / Apache Arrow** – analytical query and structured data processing.