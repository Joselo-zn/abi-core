# Agent Communication & Protocols (A2A + MCP)

## Overview

This document outlines the semantic communication protocols used in ABI for inter-agent reasoning, coordination, and supervision. The main pillars are:

* **A2A** (Agent-to-Agent Protocol): An active ontology-based protocol that enables agents to communicate intentions, hypotheses, beliefs, and evaluations.
* **MCP** (Model Context Protocol): A shared context management system that coordinates memory, task rationale, and distributed cognition.

---

## 1. A2A – Agent-to-Agent Protocol

A2A provides the semantic layer and interaction schema that allows agents to:

* Share observations and hypotheses.
* Propose actions or conclusions.
* Validate, challenge, or support other agents' proposals.

### 1.1 Message Types

* `OBSERVATION`: Raw data, factual input.
* `HYPOTHESIS`: A proposed interpretation or model.
* `CHALLENGE`: Request for clarification or rejection.
* `SUPPORT`: Agreement or reinforcement.
* `ACTION_PROPOSAL`: Suggestion to execute an operation.
* `EVALUATION`: Meta-judgment on quality, risk, or coherence.

### 1.2 Ontological Format

All messages use active semantic structures:

```json
{
  "@type": "HYPOTHESIS",
  "@context": "https://schema.abi.org/context",
  "agent_id": "agent_42",
  "claim": "Water consumption increased 20% in Zone B.",
  "confidence": 0.88,
  "evidence": ["/data/zoneB-2025-Q1.json"]
}
```

---

## 2. MCP – Model Context Protocol

MCP defines how agents:

* Manage shared memory and distributed logs.
* Retain context across interactions.
* Evaluate decisions and learn from outcomes.

### 2.1 Core Concepts

* `context_id`: A unique context reference.
* `memory_type`: (`ephemeral`, `persistent`, `event-based`, `semantic_vector`)
* `trace_log`: Immutable record of reasoning steps.
* `explanation`: Justification for decisions.

### 2.2 Context Propagation

MCP enables propagation of semantic memory and execution traces between agents:

```json
{
  "context_id": "alpha-mission-087",
  "agent_id": "planner_3",
  "memory_type": "semantic_vector",
  "inputs": ["goal: optimize water usage"],
  "outputs": ["suggestion: re-route irrigation"]
}
```

---

## 3. Compatibility and Extensibility

Both A2A and MCP are designed to:

* Use JSON-LD, RDF, OWL for extensibility.
* Work over HTTP, WebSockets, or local IPC.
* Support both structured and symbolic communication.

---

## 4. Security & Validation

* All inter-agent communication must be signed (Sigstore or equivalent).
* Logs must be immutable (Wazuh, Loki, etc).
* Semantic validation should use schemas (JSON Schema, SHACL).

---

## 5. Next Steps

* Define A2A vocabularies for common ABI tasks.
* Implement MCP context gateway in MVP.
* Create sandbox to simulate agent reasoning via these protocols.

---

*This document is part of the ABI documentation series. Contributions and proposals are welcome.*
