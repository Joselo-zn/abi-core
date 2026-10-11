# Run Progress — Showing What Your Agent Is Doing

```{note}
**Alpha.** The `phase` keys are new. Agents that don't send them keep
working exactly as before.
```

While your agent works, the Chainlit UI (`abi-core ui chainlit`) shows one progress step for the whole run. If your status updates declare a **phase**, that step becomes a readable timeline instead of a single line of status text:

```
◆  Diseñando el plan · 23s
   │ ✓ Solicitud entendida · 1.2s
   │ ✓ Estrategia elegida · 0.4s
   │ ● Diseñando el plan… · 22s
   │ ○ Esperando tu aprobación
```

- The step's title is the current phase in plain words, plus how long the run has taken so far.
- The ◆ next to it is animated while the run is going, and turns gray when it's done.
- When the run ends, the step collapses to a summary (`Plan listo · 34s`, `Listo · 1m 48s`, `Falló en: Diseñando el plan · 2m 03s`). The full timeline is still there if you expand it.
- Labels follow the browser language (Spanish or English).

## Declaring a phase

Pass `phase=` to `AgentResponse.status()`. Use a `RunPhase` value:

```python
from abi_core.agent.agent_response import AgentResponse, RunPhase

@agent.task(name="report")
async def report(query):
    yield AgentResponse.status("Analyzing request...", phase=RunPhase.ANALYZING.value)
    plan = await make_plan(query)
    yield AgentResponse.status("Planning...", phase=RunPhase.PLANNING.value)
    ...
```

| `RunPhase` | Shown while running | Shown when done |
|---|---|---|
| `ANALYZING` | Entendiendo tu solicitud / Understanding your request | Solicitud entendida / Request understood |
| `ROUTING` | Decidiendo cómo resolverlo / Deciding how to solve it | Estrategia elegida / Strategy chosen |
| `PLANNING` | Diseñando el plan / Designing the plan | Plan diseñado / Plan designed |
| `BUILDING` | Preparando agentes / Preparing agents | Agentes listos / Agents ready |
| `EXECUTING` | Ejecutando · paso i de n / Running · step i of n | Ejecución completa / Run complete |
| `SYNTHESIZING` | Redactando la respuesta / Writing the answer | Respuesta lista / Answer ready |

A new timeline entry starts each time the phase changes. Repeated updates for the same phase, such as heartbeats, only refresh the elapsed time.

The free-text message is still sent, and is what clients that don't know about phases display.

### Heartbeats

If you wrap long work in `_run_with_heartbeat`, pass the same `phase=` so every heartbeat says which phase is still running:

```python
async for item in self._run_with_heartbeat(
    call_planner(query), context_id, task_id, "Planning...",
    phase=RunPhase.PLANNING.value,
):
    ...
```

Heartbeats tell the UI which phase is still running. The elapsed time itself is refreshed by the UI every second while the run is going, so it never sits frozen between heartbeats.

## Detail and plan tasks

Optional keys that make the timeline more specific:

| Key | Effect |
|---|---|
| `phase_detail` | A short line under the current phase (`↳ Builder is creating the agent`). Newlines are collapsed and it is cut at 120 characters. |
| `task_key`, `task_label` | Opens a sub-step per plan task. A label like `task_2: Implement movement` is shown as `Paso 2/3 · Implement movement`. |
| `task_index`, `task_total` | The task's 1-based position, used in the title (`Ejecutando · paso 2 de 3`) and in the sub-step name. |
| `running_task_keys`, `running_task_indices` | The plan tasks still running when this update was sent (independent tasks run in parallel). Sub-steps close when their task leaves this list, and the title lists every running step: `Ejecutando · pasos 2, 3 y 4 de 5`. |
| `task_deliverable` | The file the task produces. While the task runs, its sub-step says `Trabajando en game_logic.py…` instead of the agent's generic heartbeat. When the agent's result payload arrives (`status` / `uploaded_artifacts`), the sub-step shows `✓ Archivo generado: game_logic.py` and the agent's message, never internal storage URLs. |

```python
yield AgentResponse.status(
    text,
    phase=RunPhase.EXECUTING.value,
    phase_detail=text,
    task_key="task_2", task_label="task_2: Implement movement",
    task_index=2, task_total=3,
)
```

The bundled orchestrator (`abi_agents.orchestrator`) already sends all of these.

## Setting up the UI

A UI created with `abi-core add chainlit` is set up already.

To add it to an existing Chainlit UI project:

1. **Stylesheet.** `abi-core` installs `public/abi/abi-run.css` and the avatars `public/avatars/abi_running.svg` and `abi_idle.svg` when the UI starts. If `.chainlit/config.toml` has no `custom_css`, point it there:

    ```toml
    [UI]
    custom_css = "/public/abi/abi-run.css"
    ```

    If you already have your own stylesheet, import it on the first line of that file instead:

    ```css
    @import url("/public/abi/abi-run.css");
    ```

    This makes Chainlit's loading dot use the animated ◆, and hides the dot once the progress step is visible, so only one indicator shows at a time.

2. **Translations.** Chainlit puts "Using"/"Used" in front of every step title, which reads badly before a phase ("Using Designing the plan"). Blank both keys in `.chainlit/translations/<lang>.json` for each language you use:

    ```json
    "status": {
        "using": "",
        "used": ""
    }
    ```

    To generate every missing translation file with these two keys already blank, run:

    ```bash
    python -m abi_core.ui.translations .chainlit/translations
    ```

    Existing files are never overwritten.

## Leaving and coming back

A run keeps going when the user switches to another conversation. When they come back to it, the progress step picks up where the run is: the step shows as running again, the elapsed time keeps counting every second, new sub-steps and the final answer appear when they arrive, and the stop button works and stops the run itself.

This needs the conversation history database (`DATABASE_URL`, the same one that keeps past conversations in the sidebar). The page that comes back follows the run through that database rather than through the process running it, so it also works when the UI runs as several replicas.

- **How a run is recognized.** The run's step carries an `abi_run` entry in its metadata: its state, what it is doing, and a heartbeat written every 5 seconds.
- **Interrupted runs.** If a run stopped writing its heartbeat more than 30 seconds ago (for example, the UI restarted mid-run), coming back shows it as `Interrumpido · <time>` instead of a step that looks like it runs forever.
- **Stop from a page that came back.** The request is stored on the conversation, and the run checks it every second, so it stops within about a second wherever it runs.
- **Database writes.** The elapsed time on screen updates every second, but the database only gets the heartbeat every 5 seconds plus real changes (a new phase, a task's update, the end of the run).

## Next step

👉 [Testing Agents](05-testing-agents.md)
