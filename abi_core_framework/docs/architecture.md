# ABI Architecture Overview

## Purpose

This document outlines the architectural vision of ABI (Agent-Based Infrastructure) — a modular, layered, and auditable system designed to empower distributed superintelligence under human supervision.

---

## 🔲 Layered Architecture

ABI is designed around **four primary layers**, each with distinct responsibilities:

### 1. Physical Infrastructure & Orchestration

* **Kubernetes** for container orchestration and logical isolation.
* **Docker** for agent/service encapsulation.
* **Terraform** for IaC and repeatable deployments.
* **Prometheus + Grafana** for observability.
* **Vault / Sealed Secrets** for secure secret management.

### 2. Cognitive Layer (Intelligent Agents)

* **Agents built with Python** (FastAPI / Langchain / Haystack).
* **LLMs running locally** (Ollama, LM Studio).
* **External models** via MCP Client (GPT-4o, Claude, Mistral, LLaMA).
* **MCP Toolbox** for reasoning, validation, memory management.
* **Vector DBs** (Weaviate, ChromaDB) for semantic memory.
* **Redis / SQLite** for per-agent state.

### 3. Semantic & Context Layer

* **MCP (Model Context Protocol)** for shared memory, distributed reasoning.
* **A2A (Agent-to-Agent Protocol)** for ontological communication.
* **JSON-LD / RDF / OWL** for structured semantic representation.
* **Schemas (YAML / JSON)** to define rules/configs per agent.

### 4. Security & Governance

* **Keycloak** for identity/authentication.
* **OPA (Open Policy Agent)** for policy enforcement.
* **Immutable logs** (Sigstore, Loki, Wazuh).
* **Isolation tools** (Firecracker, Airgap).

---

## 📦 Modular Components

### ✅ MCP Client

* Connects ABI to external or local LLMs
* Handles API authentication, tokenization, output parsing

### ✅ MCP Toolbox

* Composable tools for semantic routing, memory sync, A2A flows
* Supports runtime constraints, semantic scoring, agent state

### ✅ Agents

* Self-contained microservices
* Follow semantic interface contracts
* Can reason, act, observe, or verify

---

## 🧠 Reasoning Modes

* **Centralized** (single orchestrator agent)
* **Distributed consensus** (weighted voting, challenge-response)
* **Role-specialized** (observer → proposer → verifier)

Each mode can be selected depending on context, criticality, and performance.

---

## 🚦 Control, Traceability, and Human Oversight

* Human veto always available
* All inter-agent communication logged
* Emergency stop mechanism mandatory
* Access control enforced via IAM + signed policies

---

## 📡 Network Topologies

* ABI supports:

  * Local-only networks (air-gapped research labs)
  * Hybrid (on-prem + cloud agents)
  * Fully cloud-native with zero-trust mesh

Agents communicate through A2A over WebSockets, gRPC or message queues, depending on the latency and reliability needs.

---

## 🔧 Dev & Deployment Patterns

* **Dev containers** with pre-configured agent environments
* **Snapcraft & Docker Compose** for single-node prototypes
* **Helm & GitOps** for large-scale deployments
* **CI/CD** via GitHub Actions or Gitea + Woodpecker

---

## 🚀 Next Step

> Begin with a reference implementation of a minimum viable ABI node:
>
> * 1x orchestrator agent
> * 2x worker agents (observe + act)
> * 1x verifier agent
> * Connected to MCP Client running GPT-4o
> * Logging & policy layer active

---

## 🏗️ Modular Architecture (v1.5.2)

ABI-Core now features a **modular monorepo structure** for enhanced maintainability and community collaboration:

```
packages/
├── abi-core/          # Core libraries (common/, security/, opa/, abi_mcp/)
├── abi-agents/        # Agent implementations (orchestrator/, planner/)
├── abi-services/      # Services (semantic-layer/, guardian/)
├── abi-cli/           # CLI and scaffolding tools
└── abi-framework/     # Umbrella package with unified API
```

### Benefits

- **Backward Compatible**: All existing imports continue to work
- **Modular Development**: Each package can be developed independently
- **Community Friendly**: Easier to contribute to specific components
- **Deployment Flexibility**: Deploy only the components you need

### Enhanced Web Interfaces

- **Open WebUI Compatibility**: Fixed connection issues and improved streaming
- **Template Consistency**: Synchronized web interfaces across all agents
- **Better Performance**: Optimized HTTP connection management

---

Document version: `v1.5.2`
Maintainer: [José Luis Martínez](https://github.com/Joselo-zn)
