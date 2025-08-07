# 👁️ worker-observe/

The `worker-observe` agent is responsible for perception tasks — extracting data, detecting anomalies, or monitoring states. It plays a crucial role in grounding actions in observable facts.

---

## 🎯 Role

- Collect information from APIs, sensors, logs, or databases.
- Evaluate environmental or contextual cues for decision-making.
- Generate semantic observations to feed into shared memory (MCP).
- Respond to orchestrator assignments for observation tasks.

---

## 📦 Folder Structure

worker-observe/
│
├── main.py # Entry point for the observation agent
├── observer.py # Core logic for collecting and formatting observations
├── config.yaml # Task rules and data sources
├── context.py # Interface with MCP Client
├── a2a_protocol.py # A2A communication layer
└── requirements.txt # Python dependencies


---

## 🧠 Stack

- `Python 3.10+`
- `FastAPI` – API layer for interactions
- `MCP Client` – Access to context and task dispatching
- `A2A Protocol` – Semantic communication between agents
- `LangChain` or `Haystack` – Optional wrappers for complex extraction
- `TinyDB` – Local lightweight persistence
- `Redis` – Real-time pub/sub communication (optional)

---

## ⚙️ Sample Endpoints

- `POST /observe` – Perform an observation task (URL, system, input)
- `GET /status` – Report readiness and last observation
- `POST /context` – Push observation into shared context

---

## 🧩 Integration

- Receives assignments from the `orchestrator`
- Shares its output with the `verifier` and `auditor`
- Can chain into `worker-act` for reflex-style behaviors

---

## 🚀 Usage

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8502

Example Task:

{
  "task": "monitor_web_status",
  "target": "https://example.com/health",
  "method": "GET",
  "expected_status": 200
}

