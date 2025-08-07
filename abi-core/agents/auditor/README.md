# 🕵️ auditor/

The `auditor` agent is responsible for logging, monitoring, and validating the behavior of other agents across the ABI system.

It ensures that all interactions, actions, and decisions are recorded immutably and auditable by humans, in compliance with ABI governance rules.

---

## 🎯 Role

- Listens to agent communications and actions.
- Generates immutable logs for inspection and post-mortem analysis.
- Flags rule violations, unauthorized behaviors, or anomalies.
- Optionally integrates with external logging systems (e.g., Loki, Sigstore).

---

## 📦 Folder Structure

auditor/
│
├── main.py # Entry point for the auditing agent
├── config.yaml # Audit rules, thresholds, endpoints
├── logger.py # Core audit logging logic
├── events.py # Schema for audit events
├── storage.py # Interface for saving logs (local or remote)
└── requirements.txt # Python dependencies


---

## 🧠 Stack

- `Python 3.10+`
- `FastAPI` – optional API layer for querying audit data
- `TinyDB` / `SQLite` – local storage of audit logs
- `Redis` – optional: subscribe to inter-agent activity
- `Sigstore` / `Loki` – optional integration for immutability
- `Pydantic` – for structured audit events

---

## 🔍 Audit Types

- Agent startup/shutdown
- Task received/completed
- Validation results
- Errors or exceptions
- Violations of ABI governance rules

---

## 🔐 Example Governance Rule Enforcement

If an agent tries to access the internet or writes beyond allowed disk usage, the auditor logs the event and notifies human supervisors.

---

## 🚀 Usage

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8504
