# 🧱 ABI Technology Stack

What ABI-Core actually uses today.

---

## Runtime & Framework

| Technology | Role |
|-----------|------|
| Python 3.11+ | Core language for all agents and services |
| FastAPI + uvicorn | HTTP/REST endpoints for each agent, SSE streaming |
| Pydantic | Data validation and configuration models |
| Click | CLI command framework (`abi-core` commands) |
| Rich | Terminal formatting for CLI output |
| Textual | Interactive TUI dashboard (`abi_core.tui`) |
| Jinja2 | Template engine for project scaffolding |

## AI & LLM

| Technology | Role |
|-----------|------|
| Ollama | Local LLM inference — no API keys, no data leaves your network |
| LangChain + LangChain-Ollama | LLM integration, tool binding, structured output |
| LangGraph | Agent workflow state machines |
| nomic-embed-text | Embedding model for semantic search |

## Protocols & Communication

| Technology | Role |
|-----------|------|
| MCP (Model Context Protocol) | Semantic tool/agent discovery, HMAC-authenticated tool calls |
| A2A SDK | Agent-to-Agent communication with streaming |
| FastMCP | MCP server implementation for the semantic layer |
| httpx | Async HTTP client for SSE streaming and inter-service calls |

## Semantic Layer

| Technology | Role |
|-----------|------|
| Weaviate | Vector database for agent cards, tool cards, embedding search |
| Embedding Mesh | Distributed embedding computation and caching |
| Agent Cards (JSON) | Structured agent identity, capabilities, and skills |

## Security & Governance

| Technology | Role |
|-----------|------|
| OPA (Open Policy Agent) | Policy engine — immutable core policies, risk scoring, access control |
| Guardian Agent | Security gate — prompt injection detection, policy compliance |
| HMAC signing | Authentication for MCP tool calls between agents |
| Audit logs | Immutable decision traceability |

## Containers & Infrastructure

| Technology | Role |
|-----------|------|
| Docker | Container runtime for all agents and services |
| Docker Compose | Orchestration — one command to start everything |
| Docker SDK (Python) | Programmatic container lifecycle for ephemeral agents |
| MinIO (boto3) | S3-compatible artifact storage for ephemeral outputs |

## Graphs & Orchestration

| Technology | Role |
|-----------|------|
| NetworkX | Workflow graph construction (AgentInteractionFlow) |
| ToolExecutionGraph | DAG execution engine for `@agent.step()` pipelines |

## Project Structure

| Technology | Role |
|-----------|------|
| setuptools + pyproject.toml | Monorepo packaging — single `pip install abi-core-ai` |
| YAML (runtime.yaml) | Project configuration — agents, services, interface |

---

## Not Used (mentioned in older docs)

These were in the original vision but are not part of the current implementation:

- Kubernetes / Helm / Terraform — Docker Compose handles orchestration
- Redis / RabbitMQ — not needed for current pipeline
- Keycloak — OPA + Guardian handle security
- Neo4j — Weaviate handles semantic storage
- Vue.js / Next.js — TUI is the primary interface, webapp is FastAPI-based
- OpenTelemetry / Grafana — not yet implemented (potential future addition)
