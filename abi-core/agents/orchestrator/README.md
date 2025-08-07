# 🤖 orchestrator/

The `orchestrator` agent coordinates task distribution and inter-agent communication within the ABI system.

It does **not** centralize cognition — instead, it serves as a scheduler and mediator for agent collaboration under human-supervised rules.

---

## 🎯 Role

- Dispatch tasks to appropriate agents (e.g., observe, act, verify).
- Relay shared context across agents using MCP + A2A.
- Track task lifecycle (assigned → in progress → completed).
- Can be overridden or guided by human input.

---

## 📦 Folder Structure

orchestrator/
│
├── main.py # Entry point for orchestrator logic
├── dispatcher.py # Handles task delegation
├── registry.yaml # Registered agents and capabilities
├── context.py # Context sharing via MCP Client
├── rules.yaml # Routing and priority rules
├── a2a_protocol.py # A2A communication layer
└── requirements.txt # Python dependencies


---

## 🧠 Stack

- `Python 3.10+`
- `FastAPI` – API layer for interaction
- `MCP Client` – Agent execution and context sharing
- `MCP Toolbox` – Challenge-response, validation, context handling
- `A2A Protocol` – Ontology-based agent communication
- `YAML` – Configuration and registry files
- `TinyDB` – Lightweight local memory store (optional)
- `Redis` – For inter-agent pub/sub (if available)

---

## ⚙️ Sample Endpoints

- `POST /assign-task` – Delegate task to worker
- `GET /status` – Report task queue and agent availability
- `POST /context` – Update shared semantic context

---

## 🚀 Usage

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8501
