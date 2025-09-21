# ✅ verifier/

The `verifier` agent is responsible for validating actions, reasoning outputs, or decisions proposed by other agents (e.g. `worker-act`, `orchestrator`) using the challenge-response model defined in the MCP Toolbox and the A2A protocol.

It acts as a semantic validator, cross-checking decisions against constraints, goals, or governance rules before allowing actions to proceed.

---

## 🎯 Role

- Receives proposed actions or outputs from other agents.
- Applies semantic validation using rules, schemas, or confidence thresholds.
- Issues confirmations, rejections, or requests for clarification.
- Publishes results to Redis or returns via REST endpoint.

---

## 📦 Folder Structure

│
├── main.py # Entry point for agent
├── config.yaml # Agent-specific config and policies
├── validator.py # Logic to validate actions / outputs
├── a2a_interface.py # A2A protocol implementation
├── toolbox_hooks.py # MCP Toolbox integration
└── requirements.txt # Python dependencies


---

## 🧠 Stack

- `Python 3.10+`
- `FastAPI` – API layer for receiving validation requests
- `MCP Toolbox` – Validation logic, challenge-response flow
- `A2A Protocol` – Semantic interpretation and schema enforcement
- `TinyDB` – Optional: local store for caching validations
- `Redis` – Optional: pub/sub or broadcast of verdicts

---

## 🧪 Example Validation Flow

1. `worker-act` proposes an action to the `verifier`.
2. `verifier` receives the proposal via REST or Redis message.
3. `validator.py` checks:
    - Conformance to policy or schema.
    - Confidence level from originating agent.
    - Required evidence (facts, sources).
4. Returns a response:
    - ✅ Valid
    - ❌ Invalid (with reason)
    - ⚠️ Needs more context

---

## 🚀 Usage

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8503
