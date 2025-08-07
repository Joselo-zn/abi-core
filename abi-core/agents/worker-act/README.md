# 🦾 worker-act/

The `worker-act` agent is responsible for executing actions based on validated plans, agent proposals, or external requests. It is the hand of the ABI — acting on decisions, interacting with systems, and producing observable change.

---

## 🎯 Role

- Execute system-level or API-based actions
- Interface with external tools, APIs, or local environments
- Log action outcomes and share results for verification
- Respond to orchestrator commands with traceable execution

---

## 📦 Folder Structure

worker-act/
│
├── main.py # Entry point for the actuator agent
├── actuator.py # Core logic to perform specific actions
├── config.yaml # Definitions of safe/allowed actions
├── context.py # Interface with MCP Client
├── a2a_protocol.py # Communication layer with other agents
└── requirements.txt # Python dependencies


---

## 🧠 Stack

- `Python 3.10+`
- `FastAPI` – API layer for control and supervision
- `MCP Client` – For context-awareness and shared decisions
- `A2A Protocol` – Semantic communication and task coordination
- `TinyDB` – Local store for recent action logs
- `Redis` – Optional real-time inter-agent coordination

---

## ⚙️ Sample Endpoints

- `POST /act` – Execute an action (defined in config or passed)
- `GET /status` – Return readiness and last action performed
- `POST /context` – Push result to shared context

---

## 🧩 Integration

- Triggered by the `orchestrator` upon task validation
- Observed and validated by the `verifier` or `auditor`
- Can collaborate with `worker-observe` for reflexive feedback loops

---

## 🚀 Usage

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8503

Example Task:

{
  "task": "send_notification",
  "channel": "email",
  "to": "admin@example.com",
  "message": "System threshold exceeded"
}

