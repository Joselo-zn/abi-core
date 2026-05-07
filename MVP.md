# ABI Swarm — Evolution from MVP to Self-Building Multi-Agent System

This document traces how ABI evolved from a proof-of-concept MVP into a functional self-building swarm, and explains the reasoning behind each major architectural decision.

---

## The Starting Point (MVP, mid-2025)

The original MVP proved that distributed agent-based infrastructure could work:

- 4 agents (Orchestrator, Planner, Actor, Guardian) running in Docker containers
- Weaviate for semantic agent discovery via MCP `find_agent`
- OPA for policy enforcement
- A2A protocol for inter-agent communication
- Basic workflow orchestration with NetworkX graphs

It worked. Agents could discover each other, communicate, and execute simple workflows. But it had fundamental limitations that blocked real-world use.

---

## Why the Actor Agent Had to Go

The Actor was a long-running agent that executed tasks. The problem: it was generic. Every task went to the same agent with the same tools. There was no way to give a specific task a specific set of tools without hardcoding them.

The question became: what if the system could create its own execution agents on demand, with exactly the tools each task needs?


This led to the **Builder + Zombie** pattern:
- **Builder** receives a task spec, resolves which tools are needed from the semantic layer, generates a config, and spawns a Docker container
- **Zombie** (the ephemeral agent) boots inside that container with injected tools, executes the task, uploads artifacts, deregisters from Weaviate, and the container dies

Why "Zombie"? Because it's born, does one thing, and dies. No state, no persistence, no cleanup needed.

This was the single biggest architectural change. It turned ABI from a static multi-agent system into a self-building one.

---

## Why the Planner Needed Steps

The original Planner produced flat task lists: "do X, then do Y." But the Builder needed more detail to create the right ephemeral agent. What tools does this task need? What model should it use? What are the actual steps inside the task?

The Planner was refactored to produce structured plans:
```json
{
  "tasks": [
    {
      "task_id": "task_1",
      "description": "Create a shell script...",
      "steps": ["write_file with content", "verify with list_files"],
      "tools_needed": ["write_file", "list_files"],
      "model": "qwen2.5:3b",
      "dependencies": []
    }
  ]
}
```

Each task now carries enough information for the Builder to create a properly configured ephemeral agent.

---

## Why the Orchestrator Needed a Security Gate

In the MVP, the Guardian was called manually or as a separate step. This meant a malicious query could reach the Planner before being validated.

The fix: the Orchestrator now runs `classify_query` and `guardian_validate` in parallel as the first step. A `gate_decision` node merges both results and decides: proceed, block, or error. Only approved queries reach the Planner.

This is not optional. Every query goes through the gate. No exceptions.

---

## Why We Needed `@agent.step()` Decorators

In the MVP, agent pipelines were wired manually — functions called functions, with no clear dependency graph. This made it hard to understand execution order, retry failed steps, or add new steps without breaking existing ones.

The `AbiCore` app runner with `@agent.step()` decorators solved this:

```python
agent = AbiCore()

@agent.step(name="step_1", input_map={"query": "$input.query"})
async def step_1(query):
    ...

@agent.step(name="step_2", depends_on=["step_1"], input_map={"data": "$step_1"})
async def step_2(data):
    ...

agent.run(MyAgent())
```

Dependencies are explicit. Data flow is declared via `$references`. Execution is deterministic — topological sort, not LLM decision. Retries are built in. Every agent in the system now uses this pattern.


---

## Why Ephemeral Agents Need Self-Deregister

When a Zombie finishes its task, it needs to remove its agent card from Weaviate. Otherwise the semantic layer would keep returning dead agents for future queries.

The problem: OPA policies blocked `unregister_agent` for ephemeral agents (they didn't have the right permissions). The solution was a dedicated MCP tool: `self_deregister_ephemeral`. This tool is specifically allowed by OPA for agents with ephemeral cards, and it handles the full cleanup: deregister from Weaviate, then `os._exit(0)` to kill the container.

---

## Why the CLI Generates Everything

In the MVP, setting up a project meant manually creating Dockerfiles, compose files, agent configs, OPA policies, Weaviate schemas, and wiring everything together. This was error-prone and slow.

`abi-core create swarm` now generates a complete project in one command:
- All agents with their configs and Dockerfiles
- Semantic layer with Weaviate and MCP server
- Guardian with OPA policies
- MinIO for artifacts
- Docker Compose with all services wired
- Interactive TUI console
- `runtime.yaml` with project metadata

The user gets a working swarm in seconds. They can then customize any part.

---

## Why the TUI Lives in abi-core, Not abi-cli

The CLI (`abi-cli`) is for scaffolding — creating projects, adding agents, managing structure. The TUI console is for operating a running project — monitoring services, viewing logs, chatting with the orchestrator.

These are different concerns. The TUI widgets and services live in `abi_core.tui` so any project can import and extend them. The scaffolding generates a `console.py` in each project that inherits from `AbiConsoleApp`. Users can customize their dashboard without touching the framework.

---

## Current State (v1.9.40+)

The E2E pipeline is functional and verified:

```
User query
  -> Orchestrator (parallel triage + Guardian security gate)
    -> Planner (structured plan with tasks, steps, tools, model)
      -> Builder (resolve tools, spawn Docker container)
        -> Zombie (execute with injected tools, upload artifacts to MinIO)
          -> Self-deregister from Weaviate, container self-destructs
            -> Orchestrator synthesizes result
```

Everything runs locally with Ollama. No API keys. No data leaves your network.

```bash
pip install abi-core-ai
abi-core create swarm --name "my-swarm"
cd my-swarm
abi-core run
```

---

For the full technical reference, see [README.md](README.md).
For the roadmap, see [ROADMAP.md](ROADMAP.md).
For the philosophy, see [MANIFIESTO.md](MANIFIESTO.md) and [WHITEPAPER.md](WHITEPAPER.md).
