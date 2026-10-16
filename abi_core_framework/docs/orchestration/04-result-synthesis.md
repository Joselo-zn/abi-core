# Result Synthesis

```{warning}
**Alpha.** ABI Swarm orchestration (Orchestrator + Planner + Builder + ephemeral
agents) is under active development and may change between releases.
```

After a workflow completes — which only happens once the user has approved the plan (see [Planner & Orchestrator](01-planner-orchestrator.md#plan-confirmation)) — the Orchestrator combines all agent responses into one coherent answer for the user.

## How it works

1. Workflow executes all tasks → each agent returns a result
2. Orchestrator collects all results; if there are artifacts (files), it generates download URLs
3. The deliverable set is verified by code (integration review: the files fit together, and the entry point runs in a sandbox)
4. The LLM writes a short description of the deliverable, in the language of the user's request
5. Code adds the verdict, any missing deliverables and the download links below that description

The model describes; it does not judge. It never sees the verification result or the links, so it cannot report a set that ran without errors as broken, or an untested one as working.

## The synthesis step (from the Orchestrator)

```python
from abi_core.common.prompts.orchestrator import build_synthesis_summary_prompt
from abi_core.common.utils import build_plan_view

# 2-3 sentences describing the deliverable, in the user's language:
# gets the user's own message, the objective and the steps (title + file).
query = build_synthesis_summary_prompt(
    user_message,                    # the user's request, as they wrote it
    plan["objective"],
    build_plan_view(plan)["steps"],
)
final_response = await invoke(config.LLM_CONFIG, query, system_prompt=config.SYSTEM_PROMPT)

# The verdict is always code's
if integration.errors or integration.execution_unverified:
    final_response += "\n\n" + integration.as_text()       # full report
else:
    final_response += "\n\n" + integration.as_pass_text()  # what was checked

final_response += format_artifact_links(artifacts)
yield AgentResponse.text(final_response)
```

`IntegrationReport.as_pass_text()` says exactly what a pass covers: the files fit together and the entry point ran in the sandbox without errors, which does not prove real use (for example, that a game plays well).

## What the user sees

```
event: status → "Analyzing request..."
event: status → "Processing..." (heartbeats)
event: status → "Synthesizing results..."
event: result → "I built a snake game in Python with pygame: the snake, food
                 and score in one module, the main loop in main.py.

                 ✅ Verified by code: the files fit together and main.py ran
                 in the sandbox for up to 15 s without errors. That does not
                 prove real use.

                 📎 Generated files:
                 - game_objects.py, main.py (download links)"
```

The verdict and the report are currently written in Spanish; the description follows the user's language.

## Artifacts

Agents can upload files (PDFs, CSVs, images) to the Artifact Store (MinIO). The Orchestrator:

1. Extracts artifact metadata from agent responses
2. Generates pre-signed download URLs
3. Adds them below the answer, by code (the model never handles links)

```python
from abi_core.common.artifact_store import generate_download_urls, format_artifact_links

await generate_download_urls(artifacts)
links = format_artifact_links(artifacts)
# "📎 report.pdf: https://minio.../presigned-url"
```

## Learning across plans

Once a workflow finishes successfully, the Orchestrator writes a summary of the plan and its tasks to long-term memory (`add_long_term_memory(topic="plan_execution", ...)`, keyed by the workflow's `task_id`). This isn't consumed by anything in the synthesis step itself — it's there for the *next* planning pass: the Planner deterministically recalls similar past plans before decomposing a new request (see [Planner & Orchestrator](01-planner-orchestrator.md#the-planner)). The write is a plain function call in code, not an LLM tool call.

## Error handling

If a workflow fails partway through:

```python
if dag_result.get("failed_node"):
    error = dag_result.get("error", "Pipeline failed")
    self._record_error(context_id, "dag_failed", error)
    yield AgentResponse.error(error)
    return
```

The Orchestrator records the error in session context so the next request is aware of what failed.

## Next step

👉 [RAG & Knowledge](../rag/01-what-is-rag.md)
