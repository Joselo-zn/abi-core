# Planner & Orchestrator

The Orchestrator is the entry point for complex requests. The Planner breaks them into smaller tasks and assigns agents. Together they coordinate multi-agent work.

## How they work together

```
User request
  → Orchestrator
    ├─ Step 1: Is this simple or complex? + Is it allowed?
    ├─ Step 2: Decision (answer directly | send to Planner | block)
    ├─ Step 3: Planner breaks it into tasks → assigns agents
    └─ Step 4: Execute tasks → combine results
  → Response to user
```

## The Orchestrator

Receives every request. Its pipeline:

1. **classify_query** — Is this simple (answer directly) or complex (needs planning)?
2. **guardian_validate** — Is this request allowed by security policies? (runs in parallel with classify)
3. **gate_decision** — Based on classification + security: respond directly, call planner, or block
4. **call_planner** — Send to Planner via A2A for task decomposition
5. **build_workflow** — Turn the plan into an `AgentInteractionFlow` with nodes for each agent
6. **execute** — Run the workflow, collect results
7. **synthesize** — Use LLM to combine all results into a coherent response

```python
# Orchestrator DAG (from main.py)
@agent.step(name="classify_query", input_map={"query": "$input.query"})
async def classify_query(query):
    text = await invoke(config.LLM_CONFIG, TRIAGE_PROMPT.format(query=query))
    parsed = clean_llm_json(text)
    return {"classification": parsed.get("classification", "complex")}

@agent.step(name="guardian_validate", input_map={...})
async def guardian_validate(query, context_id):
    # Calls Guardian agent via A2A
    ...
    return {"status": "approved", "allowed": True}

@agent.step(name="gate_decision", depends_on=["classify_query", "guardian_validate"])
async def gate_decision(classification, guardian_result):
    if not guardian_result["allowed"]:
        return {"action": "blocked", "message": guardian_result["reason"]}
    if classification == "simple":
        return {"action": "respond_direct"}
    return {"action": "call_planner"}
```

## The Planner

Receives a query and produces a structured plan:

1. **LLM decomposition** — Calls the LLM with a chain-of-thought prompt to break the task into sub-tasks
2. **parse_plan** — Extracts structured JSON from the LLM response
3. **assign_agents** — For each task, searches the Semantic Layer for the right agent

Output:

```json
{
  "status": "ready",
  "plan": {
    "objective": "Analyze Q4 sales and generate report",
    "execution_strategy": "sequential",
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

## Get orchestration in your project

```bash
abi-core create swarm --name my-system
```

This creates a complete project with Orchestrator, Planner, Builder, Semantic Layer, Guardian, and all infrastructure ready to run.

## Next step

👉 [Multi-Agent Workflows](02-multi-agent-workflows.md)
