# Planner & Orchestrator

```{warning}
**Alpha.** The ABI Swarm (Orchestrator + Planner + Builder + ephemeral agents) is
under active development. APIs, generated structure, and behavior may change between
releases. Not recommended for production yet.
```

The Orchestrator is the entry point for complex requests. The Planner breaks them into smaller tasks and assigns agents. Together they coordinate multi-agent work.

## How they work together

```
User request
  → Orchestrator
    ├─ Step 1: Is this simple or complex? + Is it allowed?
    ├─ Step 2: Decision (answer directly | send to Planner | block)
    ├─ Step 3: Planner picks a methodology, breaks it into tasks → assigns agents
    ├─ Step 4: Show the plan to the user — wait for approve / reject / modify
    └─ Step 5: (once approved) Build ephemeral agents if needed → execute tasks → combine results
  → Response to user
```

## The Orchestrator

Receives every request. Its DAG:

1. **classify_query** — Is this simple (answer directly) or complex (needs planning)? Also deterministically detects two kinds of replies that skip the LLM entirely: an answer to a pending clarification, and an approve/reject/modify reply to a plan awaiting confirmation (see "Plan confirmation" below).
2. **guardian_validate** — Is this request allowed by security policies? (runs in parallel with classify)
3. **gate_decision** — Routes based on classification + security: respond directly, call the planner, block, or (if a plan is pending) confirm/reject/re-plan.
4. **call_planner** — Send to Planner via A2A for task decomposition
5. **extract_plan** — Pull the structured plan out of the Planner's A2A response
6. **check_model_availability** — Read-only: for each task that would spin up an ephemeral agent, is its model already installed? (`@agent.tool`, see "Model availability" below) — this is the DAG's terminal node.

`build_workflow` — turning the plan into an `AgentInteractionFlow` with nodes for each agent — is **not** part of this DAG. It's a plain function the Orchestrator calls directly, and only *after* the user approves the plan, because it's the step that actually calls the Builder and creates ephemeral containers. See "Plan confirmation" below.

```python
# Orchestrator DAG (from steps.py)
@agent.step(name="classify_query", input_map={"query": "$input.query", "session_context": "$input.session_context"})
async def classify_query(query, session_context=None):
    # Deterministic short-circuits first (pending plan confirmation, pending
    # clarification) — only falls through to the LLM triage if neither applies.
    text = await invoke(config.LLM_CONFIG, TRIAGE_PROMPT.format(query=query))
    parsed = clean_llm_json(text)
    return {"classification": parsed.get("classification", "complex")}

@agent.step(name="guardian_validate", input_map={...})
async def guardian_validate(query, context_id):
    # Calls Guardian agent via A2A
    ...
    return {"status": "approved", "allowed": True}

@agent.step(name="gate_decision", depends_on=["classify_query", "guardian_validate"])
def gate_decision(triage, guardian, query):
    if guardian.get("status") == "error":
        return {"action": "system_error", "message": "..."}
    if guardian.get("status") == "blocked":
        return {"action": "blocked", "message": "..."}

    classification = triage.get("classification")
    if classification == "plan_confirmed":
        return {"action": "execute_confirmed_plan", "plan": triage.get("pending_plan")}
    if classification == "plan_rejected":
        return {"action": "plan_rejected"}
    if classification == "plan_modify_requested":
        return {"action": "plan_modify_requested"}
    if classification == "plan_modify_feedback":
        return {"action": "call_planner", "query": "...original + feedback..."}
    if classification == "simple":
        return {"action": "respond_direct"}
    return {"action": "call_planner"}
```

## The Planner

Receives a query and produces a structured plan:

1. **Pick a methodology** — Before decomposing, an LLM call chooses which decomposition approach fits the request best: WBS, SMART, GTD, or Polya's "How to Solve It" (see "Methodology selection" below). Falls back to WBS on any failure.
2. **LLM decomposition** — Calls the LLM with a chain-of-thought prompt (now including the chosen methodology's guidance) to break the task into sub-tasks
3. **parse_plan** — Extracts structured JSON from the LLM response
4. **assign_agents** — For each task, searches the Semantic Layer for the right agent

Output:

```json
{
  "status": "ready",
  "plan": {
    "objective": "Analyze Q4 sales and generate report",
    "execution_strategy": "sequential",
    "methodology": "WBS",
    "methodology_rationale": "Two independent deliverables (analysis, report).",
    "tasks": [
      {
        "task_id": "task-1",
        "type": "analysis",
        "description": "Analyze Q4 revenue data",
        "agents": [{"name": "analyst", "url": "http://..."}]
      },
      {
        "task_id": "task-2",
        "type": "generation",
        "description": "Generate PDF report from analysis",
        "agents": [{"name": "reporter", "url": "http://..."}],
        "depends_on": ["task-1"]
      }
    ]
  }
}
```

If the Planner needs more info, it returns `{"status": "needs_clarification", "clarification": "..."}` and the Orchestrator forwards it to the user.

## Plan confirmation

The Orchestrator never executes a plan the moment it's produced — the user always confirms it first ("the system proposes, the user disposes"). After `check_model_availability` runs, the Orchestrator:

1. Formats the plan as a readable summary — objective, methodology + rationale, each task, and (for tasks that need an ephemeral agent) whether the model is already installed or will be downloaded.
2. Saves the plan in the session (`SessionStore` — survives across the pause) and persists the chosen methodology to system-level short-term memory, so any agent inspecting this conversation can recover it, not just whichever one receives the next prompt directly.
3. Sends the summary with `require_user_input: true` and stops. In Chainlit this renders as three action buttons — ✅ Aprobar / ❌ Rechazar / ✏️ Modificar — not just free text.

On the next turn, `classify_query` deterministically reads the button choice (or a typed "sí"/"no") and `gate_decision` routes it:

- **Approve** (`execute_confirmed_plan`) — the Orchestrator calls `build_workflow` for real with the stored plan, and only *now* does the Builder get invoked and ephemeral containers get created.
- **Reject** (`plan_rejected`) — the session is cleared, the user gets "Plan cancelado."
- **Modify** (`plan_modify_requested`) — the Orchestrator asks what to change; the next message is treated as feedback and merged into the original query, re-entering the Planner for a new plan (which pauses for confirmation again).

If the pending plan expired (session backend restarted, or too much time passed) before the user approves, the Orchestrator says so explicitly rather than executing something that no longer matches what was shown.

### Model availability

`abi_core.common.model_tools` is a framework-level module (not specific to the Orchestrator or Builder) that maps `{model_name: host_url}` across one or more Ollama hosts, rather than a yes/no check against one hardcoded container:

```python
from abi_core.common.model_tools import list_available_models, find_model, pull_model

registry = await list_available_models()      # {"qwen2.5:3b": "http://ollama:11434", ...}
location = await find_model("qwen2.5:3b")     # host url, or None
```

- The **Orchestrator** wraps `find_model`/`list_available_models` in a read-only `@agent.tool` (`check_model_availability`) used only to build the confirmation summary — it never mutates anything.
- The **Builder** wraps `pull_model` in `ensure_model_available` (`@agent.tool`, ahead of `build_container`) so an ephemeral agent's container is never built with a missing model.

### Methodology selection

`abi_core.common.methodology_tools.list_methodologies()` is the framework's registry of decomposition methodologies (`{"WBS": "...", "SMART": "...", "GTD": "...", "Polya": "..."}`) — available to any agent, not hardcoded inside the Planner's prompt. The Planner's methodology-selection call builds its options from this registry, so it's a single source of truth.

## Get orchestration in your project

```bash
abi-core create swarm --name my-system
```

This creates a complete project with Orchestrator, Planner, Builder, Semantic Layer, Guardian, and all infrastructure ready to run.

## Next step

👉 [Multi-Agent Workflows](02-multi-agent-workflows.md)
