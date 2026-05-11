# Architecture

## System overview

```
User (curl / Postman / Open WebUI)
  │
  ▼
┌─────────────────────────────────────────────────────┐
│  Web Interface (FastAPI)                            │
│  SSE streaming, REST, webhooks                      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Orchestrator                                       │
│  DAG: classify → guardian_validate → gate_decision  │
│       → call_planner → build_workflow → execute     │
└──────────────────────┬──────────────────────────────┘
                       │ A2A
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐
     │ Planner │ │ Builder │ │ Agents  │
     │         │ │         │ │ (yours) │
     └─────────┘ └─────────┘ └─────────┘
          │            │            │
          └────────────┼────────────┘
                       │ MCP
                       ▼
┌─────────────────────────────────────────────────────┐
│  Semantic Layer                                     │
│  Weaviate (vectors) + MCP Server (tools)            │
│  Agent cards, tool cards, document storage           │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Security Layer                                     │
│  Guardian (gate) + OPA (policy engine)              │
│  HMAC auth, risk scoring, audit logs                │
└─────────────────────────────────────────────────────┘
```

## Communication protocols

| Protocol | Between | Purpose |
|----------|---------|---------|
| A2A (JSON-RPC/HTTP) | Agent ↔ Agent | Task delegation, streaming responses |
| MCP | Agent → Semantic Layer | Tool calls, agent discovery |
| HTTP/SSE | User → Web Interface | Queries, streaming responses |
| REST | Any → Health endpoints | Health checks, metrics |

## Inside an agent

```
AbiCore (app runner)
  │
  ├── @agent.step → ToolExecutionGraph (DAG)
  ├── @agent.task → Programmatic orchestration
  ├── @agent.tool → LLM-invocable functions
  └── @agent.mcp_tool → Remote tools via MCP
  │
  ▼
AbiAgent (base class)
  ├── stream() → Main execution path
  ├── LLM (via create_llm + LLM_CONFIG)
  ├── Checkpointer (conversation memory)
  └── A2A Server (auto-started by agent_factory)
```

## Execution paths in stream()

| Path | Condition | Behavior |
|------|-----------|----------|
| Path 0 | Tasks registered (`@agent.task`) | Execute first task as entry point |
| Path A | tool_graph exists (steps/tools) | Execute DAG deterministically |
| Path B | No graph, no tasks | Use LangChain agent with LLM |

## Data flow for a request

```
1. HTTP POST /stream {"query": "..."}
2. web_interface._wrap_user_query() → {"route": "...", "text": "..."}
3. agent.stream(query=json_string)
4. _resolve_task(task_id) → finds the right task function
5. task function runs:
   - yield AgentResponse.status("...")  → SSE event to client
   - await agent.execute_step("name")   → runs step function
   - step calls invoke(LLM_CONFIG, prompt) → LLM response
   - yield AgentResponse.result({...})  → SSE event to client
6. SSE stream closes
```

## Project structure

```
my-project/
├── agents/
│   ├── my-agent/
│   │   ├── app.py           ← AbiCore instance
│   │   ├── agent_*.py       ← AbiAgent subclass
│   │   ├── steps.py         ← @agent.step functions
│   │   ├── tasks.py         ← @agent.task functions
│   │   ├── tools.py         ← @agent.tool functions
│   │   ├── prompts.py       ← All prompts
│   │   ├── config/config.py ← LLM_CONFIG, ports, env vars
│   │   ├── web_interface.py ← FastAPI endpoints
│   │   ├── agent_cards/     ← Agent card JSON
│   │   ├── main.py          ← Entry point
│   │   └── Dockerfile
│   └── ...
├── services/
│   ├── semantic_layer/      ← Weaviate + MCP + embeddings
│   ├── guardian/            ← Security + OPA policies
│   └── web_api/             ← Optional frontend
├── compose.yaml
└── .abi/runtime.yaml
```
