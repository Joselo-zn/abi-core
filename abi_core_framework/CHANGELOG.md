# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- **Leftovers of the deprecated Guardian in `abi-core create project
  --with-guardian`:** the `emergency_logs/` folder, `alerting_config.json`,
  the dashboard port 8080 and its variables. The generated Guardian READMEs
  now describe its actual endpoints (`/health`, the agent card, A2A).

### Fixed
- **A rebuilt Chainlit UI could install an old abi-core-ai.** The Dockerfile
  `abi-core add chainlit` generates installed `abi-core-ai[ui]` with no
  version, so Docker could reuse a cached layer from an older build and fail;
  it now pins `>=` the version of the CLI that generated it.
- **`abi-core --version` printed a hardcoded 1.4.0.** It now prints the
  installed abi-core-ai version, like the banner (`abi_cli.__version__` too).
- **The Guardian of a generated project was unreachable from the host.**
  Its compose mapped host port 11438 to the container's 11434, while the
  Guardian listens on 11438; it now maps 11438 to 11438. In an existing
  project, change `"11438:11434"` to `"11438:11438"` in `compose.yaml`.
- **Timeouts reached users only in Spanish.** The timeout error is now in
  English and carries a code (`error_code: "timeout"`), which the Chainlit
  UI shows in the browser's language. New `AgentResponse.error(message,
  code=None)` and `AgentResponse.error_from(exc)`.
- **Confirmation buttons were always in Spanish.** Without a review card,
  the approve/reject/modify buttons now follow the browser's language.
- **A pending confirmation was labelled "Plan ready".** The progress step
  now says "Waiting for your confirmation", which also fits confirmations
  that aren't plans.

## [1.13.74] - 2026-10-11


### Added
- **LLM parameters from the deployment (`LLM_EXTRA_PARAMS`).** New
  `abi_core.agent.llm_provider.llm_config_from_env()` builds `LLM_CONFIG`
  from the environment for the reference agents, the Guardian and the agent
  template. `LLM_EXTRA_PARAMS` (a JSON object, passed as-is to the LangChain
  model) goes over the agent's own defaults, so parameters such as
  `thinking`, `thinking_level`, `max_tokens` or `api_version` no longer
  require editing code. Invalid JSON stops the agent at start-up, naming the
  variable (`parse_extra_params`). The Builder forwards
  `EPHEMERAL_LLM_EXTRA_PARAMS` to each ephemeral, and a task's own
  `llm_config` (model, `extra_params`, `temperature`) now reaches the
  ephemeral whole.
- **Ephemerals can run on their own LLM provider.** `EPHEMERAL_LLM_PROVIDER`,
  `EPHEMERAL_MODEL_NAME`, `EPHEMERAL_LLM_API_KEY` and
  `EPHEMERAL_LLM_BASE_URL` on the Builder. With a hosted provider the
  ephemeral installs `abi-core-ai[<provider>]` at start-up and receives the
  key.
- **Code execution sandbox (`abi_core.common.sandbox`).**
  `run_in_sandbox(files, command, ...)` runs code in a throwaway container:
  no network, only allowlisted environment variables, a non-root user with
  no capabilities, a read-only root with a size-limited `/workspace`, and
  wall-clock/CPU/memory/PID/output limits. The command comes from the
  caller, never from a model; output is returned as untrusted data. Images
  under `sandbox-images/` (`abi-sandbox-python`, `abi-sandbox-pygame`).
- **Governed sandbox (`SANDBOX_RUNTIME=service`).** Code runs only through
  `sandbox-service` (`python -m abi_services.sandbox_service`), the only
  component with the Docker socket. Every request is signed with the
  caller's agent card, verified by the Semantic Layer (new MCP tool
  `verify_caller`), decided by OPA (`abi/sandbox`, new `sandbox.rego`;
  denied if OPA is unreachable) and audited. New `@agent.sandboxed` and
  `sandbox_caller(run_id)`.
- **Result review for multi-file deliverables (reference agents).** When a
  plan delivers several code files, the set is checked as a whole — static
  checks and a run in the sandbox — before the answer is written. Problems
  are repaired where possible; anything still broken, or never verified, is
  appended to the answer verbatim instead of being summarized away.
  Switches: `INTEGRATION_REVIEW`, `INTEGRATION_REVIEW_SANDBOX`.
- **Runs that survive failing agents (reference agents).** If an ephemeral
  agent fails, the run continues with what arrived, and the final answer
  states exactly what was missing and how it was completed.
- **Plan-run files in the artifact store.** Each plan run keeps its files
  together; they expire after `PROJECT_RETENTION_DAYS` (default 30) through
  a bucket lifecycle rule that leaves the bucket's other rules untouched.
- **Cloud Run backend for ephemeral agents (`CONTAINER_RUNTIME=cloudrun`).**
  One Cloud Run service per ephemeral, addressed by its run.app URL; the
  Orchestrator sweeps finished services. Docker stays the default. New extra:
  `abi-core-ai[gcp]`.
- **Agent card URLs from the environment.** `"url": "${VAR:-default}"` is
  expanded by `load_agent_card` and by the Semantic Layer, so one card file
  serves local Docker and Cloud Run.
- **Semantic Layer tools** `get_ephemeral_card` (exact lookup of an
  ephemeral's card, without `auth`) and `verify_caller`.
- **`invoke(recursion_limit=..., checkpointer=...)`.** Size a tool-calling
  agent's step budget to its work, and keep its conversation beyond the call.
- **Orchestrator logs its routing decision** (`[🧭] Routing decision: ...`)
  after every reasoning turn.
- **Google OAuth login, Postgres-backed persistent threads and invite-only
  registration for the bundled Chainlit UI** (opt-in with
  `OAUTH_GOOGLE_CLIENT_ID`; otherwise the UI stays anonymous). The first user
  becomes admin, every user gets one invite to hand out, and anyone without
  one lands on a waiting list. New dependencies in the `ui` extra:
  `sqlalchemy[asyncio]`, `asyncpg`, `boto3`. See
  [Authentication](docs/production/07-authentication.md).
- **`AgentResponse.element(element_type, props, name)`.** Agents send rich
  elements (image/file/pdf/audio/video/text/dataframe/qr) rendered inline by
  a Chainlit-based UI; `qr` is rendered server-side. See
  [Rich Elements](docs/single-agent/10-rich-elements.md).
- **Custom `.jsx` elements**, with `InfoCard` and `MapEmbed` bundled and
  installed automatically.
- **Recent-error awareness.** The last error recorded for a session
  (`AbiAgent.record_error`) is shown once to the next reasoning turn, then
  cleared.
- **`write_pdf` fixed tool and `direct_tool` plan tasks.** A plan task can
  name a fixed, audited tool (`abi_core.common.library_tools.write_pdf`)
  instead of an agent; the Planner runs it directly. It still goes through
  plan confirmation.
- **`AbiAgent.record_conversation_turn` / `format_conversation_summary`.** A
  rolling window of recent turns, kept in the session backend
  (multi-pod safe); the oldest turn is promoted to long-term memory when the
  window overflows.

- **Run progress in the Chainlit UI.** Each run shows one progress step: the
  current phase in plain words (English or Spanish, following the browser),
  the elapsed time, and a timeline of done, running and upcoming phases.
  Agents declare the phase with `AgentResponse.status(..., phase=RunPhase.X.value)`
  (`RunPhase` in `abi_core.agent.agent_response`: `ANALYZING`, `ROUTING`,
  `PLANNING`, `BUILDING`, `EXECUTING`, `SYNTHESIZING`), plus optional
  `phase_detail`, `task_key`, `task_label`, `task_index`, `task_total`,
  `running_task_keys`, `running_task_indices` and `task_deliverable`.
  `_run_with_heartbeat(..., phase=...)` repeats the phase in every heartbeat.
  Plan tasks running in parallel get one sub-step each, with a readable
  result ("File created: player.py") instead of the agent's raw payload.
  Agents that send no phase work as before. The UI installs
  `public/abi/abi-run.css` and its avatars on start. Existing Chainlit
  projects must point `custom_css` in `.chainlit/config.toml` at
  `/public/abi/abi-run.css` (or `@import` it from their own stylesheet) to
  get the animated indicator; projects created with `abi-core add chainlit`
  already do. `python -m abi_core.ui.translations` generates missing
  Chainlit translations. See [Run Progress](docs/single-agent/11-run-progress.md).
- **Plan review card.** Send `plan_view=build_plan_view(plan, model_status)`
  with `AgentResponse.input_required(..., action_type="plan_confirmation")`
  and the Chainlit UI shows the plan as a card: the objective, the steps in
  execution order, notices only when needed (such as a model to download),
  and Approve / Modify / Reject — Modify takes the change inside the card.
  New: `build_plan_view` and `plan_execution_order` (`abi_core.common.utils`),
  the optional `PlanTask.title`, and `PLAN_MODIFY_FEEDBACK_SENTINEL`
  (`abi_core.agent.plan_confirmation`, classified as `plan_modify_feedback`).
  See [Plan Confirmation](docs/single-agent/09-plan-confirmation.md).
- **Coming back to a conversation with a run in progress.** The progress
  step stays live: it shows as running, the time keeps counting, new steps
  and the final answer appear, and Stop stops the real run. Works across UI
  replicas; requires the history database (`DATABASE_URL`). A run that died
  with the UI shows as interrupted instead of running forever.

### Changed
- **The reviewer's repair rules live in its role prompt.** The repair
  message no longer repeats them; it carries the findings, the agents'
  answers, missing files, allowed imports and the output format. The role
  gains two rules (imported names and call signatures must match; wire the
  main loop). Measured on four sets with injected failures: every set was
  repaired in one call, as before.
- **Code agents get a role prompt.** It says what a code agent is and how it
  works (its spec before its code, then the file, then a check against the
  spec), with the rules behind the most common integration failures:
  use only what the other files expose, write only its own file, a module
  runs nothing on import, no external files the plan does not deliver. The
  task block below it is filled from the plan and its technical design
  (file, role, responsibility, plan files, entry point, what the
  dependencies expose). The plan's methodology framing is no longer
  prepended to ephemerals, and the task message no longer repeats the
  tool list the model already receives.
- **Orchestrator routing prompt covers every action.** It described two of
  the four actions the routing schema offers; it now explains all four,
  says to answer in the user's language, and drops a rule the schema
  already enforces.
- **Synthesis, document content and plan confirmation prompts rewritten.**
  The synthesis message gives its instruction once, before the run's data.
  Document content (`direct_tool`) is written in the request's language and
  leaves visible placeholders instead of inventing facts. The plan
  confirmation is decoded against a schema, so its decision is always one
  of approve, reject, modify or unrelated.
- **Every prompt in one place: `abi_core.common.prompts` is now a package**
  with one module per agent. All the text the framework and its agents send
  to a model lives there, unchanged. Every old import path keeps working.
- **A hosted provider no longer receives the Ollama server as `base_url`.**
  `OLLAMA_HOST` is the default `base_url` for Ollama only. The Guardian now
  reads `LLM_BASE_URL`, `LLM_API_KEY` and the cloud keys like the other
  agents.
- **Guardian and generated agent cards no longer set `temperature`.**
- **Role prompts of the reference Planner, Builder and Orchestrator
  rewritten** (`abi_core.common.prompts`); the Orchestrator's synthesis call
  now has a system prompt.
- **`execute_step` honours the step's declared `timeout`**, as the DAG does.
- **`SessionStore`'s TTL is a sliding window.** `resolve()` renews the expiry
  on every use: only a session idle for the full `SESSION_TTL` expires.
  `/stream` sets `X-Session-Resolved: false` when a token didn't resolve, and
  `AgentStreamClient` drops its cached token on that signal. See
  [Sessions & Multi-turn](docs/single-agent/07-sessions-multi-turn.md#token-expiry-is-a-sliding-window-not-a-fixed-deadline).
- **`record_error` / `record_pending_plan` / `clear_pending_plan` moved to
  `AbiAgent`**, with `AbiCore` passthroughs. No behaviour change.
- **`AbiAgent._run_with_heartbeat()` / `_run_llm_turn()` are async
  generators** that yield each heartbeat as it happens and end with a
  `_HeartbeatDone(result)` sentinel. `max_wait` has no default cap. Breaking
  for subclasses that called `_run_with_heartbeat` with the old
  `await ... -> (result, heartbeats)` shape.
- **`EXECUTION_TIMEOUT` default 600 → 3600**, now a last-resort backstop:
  ephemeral work is bounded by real progress (a stalled model stream, a
  memory call's own timeout), not by a flat clock.
- **Chainlit UI:** one progress step per plan task, so each task stays
  visible instead of being overwritten by the next.
- **The plan text no longer shows internal details.** `format_plan_summary`
  leaves out the internal methodology and infrastructure URLs, and a task
  without an agent reads "A new agent will be created".

### Removed
- **`abi-core run --mode`.** It only changed the banner; nothing read the
  mode it exported.
- **The TUI (`abi_core.tui`), deprecated in favour of the web interface
  (Chainlit).** Removed the package, the `textual` dependency, the
  `console.py` that `abi-core create project` generated, and `abi-core run`'s
  TUI mode (`--no-tui`, `interface.enabled` in `runtime.yaml`). An existing
  `console.py` fails on import from this version on; delete it.
- **`abi-core add service guardian` and `guardian-native`.** Both generated
  broken services. The Guardian is created with the project
  (`abi-core create project --with-guardian`).
- **`abi-core add abi-swarm`, `abi-core create swarm`, `abi-core remove
  abi-swarm`.** The combined Orchestrator + Planner + Builder system is now
  its own product, ABI Swarm. The reference agents stay in `abi_agents`; see
  [Planner & Orchestrator](docs/orchestration/01-planner-orchestrator.md).
- Unused prompts `ORCHESTRATOR_QA_COT_PLANNER`,
  `ORCHESTRATOR_PLANNER_SUMMARY`, `VERIFIER_COT_INSTRUCTIONS`,
  `OBSERVER_COT_INSTRUCTIONS` and `ORCHESTRATOR_TRIAGE_PROMPT`.
- Unused prompts `ZOMBIE_AGENT_PROMPT` and `WORKER_COT_TASK`, and a
  duplicate definition of `WORKER_PROMPT`.

### Fixed
- **New agents and MCP services could not build their image.** The
  `abi-core-ai` pin in the scaffolding was glued to the following text, and
  pip rejected it (`Invalid requirement`); the project template silently
  dropped `fastapi`. Each pin is now on its own line.
- **The generated web interface sent malformed SSE events** (`ping`, `done`,
  `error` carried a literal backslash-n instead of a line break).
- **Every Open WebUI user shared one conversation.** A generated agent's
  `/api/chat` and `/api/generate` used a fixed session. They now use one
  session per Open WebUI user and chat, from the user JWT Open WebUI signs
  (`OPENWEBUI_JWT_SECRET` on the agent, same value as Open WebUI's
  `FORWARD_USER_INFO_HEADER_JWT_SECRET`), or the agent's session token. An
  identity that does not verify is rejected (401); `ABI_SESSION_REQUIRED`
  applies as on `/stream`.
- **`/api/generate` streamed in the chat format.** A generated agent's
  Ollama-compatible `/api/generate` sent its streamed text in
  `message.content`, where Ollama clients don't look for it; it now uses
  `response`, as Ollama does. `/api/chat` is unchanged.
- **The agent stream sent Python text instead of JSON.** A response
  (`AgentResponse`) went out as the Python repr of a dict inside `message`;
  it is now a JSON object. Existing clients that use `parse_agent_message`
  (the Chainlit UI) read both.
- **`abi_core.client` exported nothing.** `AgentStreamClient` and
  `parse_agent_message` are now importable from `abi_core.client`.
- **`abi-core add policies` created policies that were never applied.** It
  wrote them outside the folder OPA loads, in a package the Guardian does
  not evaluate. It now writes to `services/guardian/opa/policies/` in the
  `abi.custom` package (custom policies add up), refuses in a project
  without a Guardian, and reminds you to restart OPA.
- **`tool_list_agents` always failed.** It read a resource no Semantic Layer
  defines. It now calls `recommend_agents` and returns agent cards; new
  optional `max_agents` (default 5). An agent card that restricts
  `security.allowed_mcp_tools` must list `recommend_agents`; the scaffolded
  Guardian policy now grants it to its example users too. In an existing
  project with user validation on, add `recommend_agents` to the users'
  `allowed_tools` in `semantic_access.rego`.
- **`@agent.mcp_tool` with a wrapper function never called the MCP tool.**
  The wrapper now receives the node's inputs and returns the call's
  arguments (a dict); the node's output is the tool's result.
- **`MCPToolkit.call` returned only part of a list**, and an empty list as
  `{}`. It now returns the tool's `structuredContent` when the server sends
  one.
- **`invoke(thread_id=...)` was documented as conversation memory.** On its
  own it keeps nothing between calls; the docstring now says so.
- **CLI banner named another product.** It now reads "ABI-Core —
  Agent-Based Infrastructure Core".
- **A2A messages without `"kind"` went out empty.** A part with `text` and
  no `kind` is now treated as text.
- **A2A policy denials and invalid requests are no longer retried.**
  `agent_connection` raises `A2APolicyDenied` (a `PermissionError`) for a
  policy decision; connection failures stay a plain `PermissionError` and
  are retried.
- **Gemini message content arriving as a list of blocks crashed
  tool-calling agents** on their final answer.
- **Ephemerals could not make A2A calls.** The Builder now passes `OPA_URL`
  and `GUARDIAN_URL`; without them, `strict` mode denied every call.
- **Ephemerals of the same run could not talk to each other.** The
  scaffolded A2A policy now allows calls within a run, and only within it.
  New tasks are no longer assigned to a previous run's ephemerals (agent
  lookups for new work use `exclude_ephemeral=True`).
- **An ephemeral that couldn't deliver its work stayed alive indefinitely.**
  It now ends after a bounded retry.
- **Plans in the same conversation could read each other's intermediate
  state.** Each plan run now has its own id.
- **Tasks didn't receive the output of the tasks they depend on.** The
  dependency files were never downloaded (`download_artifacts` didn't
  exist), used the wrong storage keys, and dependents could be built before
  their dependencies. Ephemerals also didn't share the Orchestrator's
  session store — set `SESSION_BACKEND`/`SESSION_REDIS_URL` on the Builder,
  which now forwards them.
- **A task with several dependencies ran once per dependency.**
  `AgentInteractionFlow.add_edge` now accepts a list and builds a real
  "wait for all" join.
- **A plan with fully independent tasks ran only the first one.** Every
  entry node is now connected to the graph's start.
- **Task progress never reached the client during plan execution.** Workflow
  nodes now stream each event as it arrives (`stream_mode=["custom",
  "updates"]`), and the Orchestrator relays heartbeats that arrive as status
  updates.
- **Heartbeats were batched instead of live.** Fixed by the generator
  rewrite above.
- **The stall watchdog on tool-calling streams fired on healthy
  generations.** Streams are read token by token; the wait for the first
  token is unbounded, and the stall timeout applies only once tokens flow. A
  timed-out step now reports its real cause.
- **Tool-calling `invoke()` had no stall protection** and could block the
  event loop. It now bounds each chunk's wait, with one retry on a fresh
  client (opt-in via `call_timeout`).
- **Tool-calling agents were capped at ~5 tool calls.** See
  `invoke(recursion_limit=...)` above.
- **Docker SDK calls had no timeout of their own.** `run_container` /
  `destroy_container` now bound the wait.
- **A healthy ephemeral was declared dead after 60 s.** The Builder now
  waits while the container is alive (`EPHEMERAL_HEALTH_TIMEOUT`, default
  300 s) and stops as soon as it exits; an ephemeral that never becomes
  healthy is destroyed.
- **The per-task model override was pulled but not used.**
- **An ephemeral that rewrote one of its input files never uploaded it.**
- **Service cards were rejected by the semantic access policy** (no `id`);
  `service_id` is now used as `id`.
- **pygame sandbox image: audio unavailable.** The image now installs
  `libglib2.0-0` (rebuild `abi-sandbox-pygame`).
- **Download links (and their QR codes) used an internal Docker hostname.**
  New `ARTIFACT_PUBLIC_ENDPOINT` is used for links handed to people; it must
  point at MinIO's S3 API port, not the Console. See
  [Artifact Store](docs/production/05-artifact-store.md).
- **The Chainlit progress step appeared below the answer it precedes.**

## [1.13.31] - 2026-09-11

### Changed
- **Orchestrator routing decision unified into a single deterministic contract**
  — the reasoning turn used to branch into three separately-coded paths
  (delegate/don't, plan-pending, clarification-pending), each with its own
  drifting criteria for "what's the LLM allowed to choose" and "what happens
  if it doesn't choose anything". Replaced with one deterministic step
  (`steps.py::build_routing_contract`) that always produces the same
  `{query, pending_plan_summary, pending_clarification_question,
  valid_actions}` shape, and one structured-output call
  (`with_structured_output(method="json_schema")`, not tool-calling — Ollama
  ignores `tool_choice`, verified against the installed langchain-ollama
  source) forced to a dynamic `Literal[*valid_actions]` schema. Removes
  `_should_have_delegated`/`_enforce_create_plan`, the probabilistic
  "did-you-mean-to-delegate" retry that broke production (forced a
  nonsensical `create_plan` call for "Hola como te llamas", crashing the
  Planner's `parse_plan` on the malformed result).
- **`resolve_pending_plan` (the only decision that triggers real
  `build_workflow`/Docker execution) uses a separately-profiled model**
  — `qwen3:latest` (the routing default) got the approve/reject/modify
  sub-decision wrong ~60% of the time regardless of schema shape (tested:
  nested+optional, nested+required, flattened, few-shot prompting) or model
  size (tested up to 24B — bigger didn't help, one 8B model did worse).
  `qwen3:latest` with `reasoning` disabled closed the gap (9/10 on approve
  phrasings) at practical latency (13s/call, 21x faster than with its
  "thinking" mode on) — capability profile, not size, was the variable that
  mattered. New `config.ROUTING_DECISION_LLM_CONFIG`, used only for this
  decision.
- **Dependency floors bumped to latest for packages with no reported breaking
  changes** — `cryptography`, `starlette`, `redis`, `a2a-sdk`, `langchain`,
  `langgraph`, `langchain-ollama`, `langchain-community`, `fastapi`,
  `uvicorn`, `click`, `rich`, `docker`, `boto3`, `tinydb`, `requests`,
  `numpy`, `textual`, `chainlit`, `langchain-openai`, `aiohttp`. Verified
  after install: core module imports, `Part.data`/`new_data_part` round-trip
  against `a2a-sdk` 1.1.2, and `RedisSessionBackend` create/resolve/destroy
  against a real Redis instance (redis-py 8.1.0, RESP3 default). `numpy`
  floor is `2.4.6`, not `2.5.x` — `2.5.0` dropped Python 3.11 wheels, and
  this project's `requires-python` is `>=3.11`; `2.4.6` is the latest
  release that still ships one.
- **`mcp`/`fastmcp` deliberately NOT bumped past 1.x/3.x** — `mcp` 2.0 is a
  protocol-level rewrite (drops the streamable-HTTP `initialize` handshake
  this framework relies on, `ctx.elicit()` raises `NoBackChannelError` on
  modern connections, new hard `opentelemetry-api` dependency); `fastmcp`
  4.x tracks it. Pinned `mcp>=1.26.0,<2` and `fastmcp>=3.2.0,<4` explicitly
  so a routine `pip install -U` can't pull them in by accident. v1.x/3.x
  remain on security-fix-only maintenance upstream.

### Fixed
- **Ephemeral (zombie) agents left `qwen3`'s "thinking" mode on by default**,
  same root cause already fixed everywhere else in the framework
  (`orchestrator`/`guardian`/`planner`/`builder` config, above) but missed
  here because ephemeral agents use a separate, dynamically-generated config
  template never touched by that fix. Confirmed live: an
  `EPHEMERAL_MODEL_NAME=qwen3:latest` agent hit its own `EXECUTION_TIMEOUT`
  (600s, `analyze_and_execute`) — not because the timeout was too short, but
  because thinking-mode-on inflates even simple calls ~20x (measured
  elsewhere in this framework: ~277s vs ~13s). `zombie/agent/config/config.py`
  now sets `extra_params={"reasoning": False}` when `LLM_PROVIDER=ollama`,
  matching the other 4 services.

## [1.13.21] - 2026-09-08

### Fixed
- **Orchestrator leaked raw A2A protocol objects into the client SSE stream**,
  crashing the UI with `'str' object has no attribute 'get'` after approving a
  plan. `orchestrator.py`'s execution loop yielded each `workflow.run_workflow()`
  chunk directly instead of through `AgentResponse` — those chunks are raw
  `a2a_pb2.StreamResponse` protobuf instances, and `yield_chunk_data()`'s
  `.__dict__` fallback serializes the wrong thing for that type (the *class's*
  dict, not the message fields), producing an unparseable string instead of
  JSON. Now parsed with `A2AResponse.parse()` before yielding, same as the
  artifact-extraction code right below it.
- **A single global 180s timeout (`ABI_REASONING_TIMEOUT`) capped both routing
  decisions and real DAG/tool-calling work**, cutting off ephemeral agents
  before they finished legitimate long-running tasks (e.g. generating a full
  game with a 24B-parameter model on CPU). `@agent.step()` now accepts a
  per-step `timeout`; DAG-wide execution uses its own, more generous cap
  (`ABI_DAG_MAX_WAIT`, default 900s) instead of sharing `ABI_REASONING_TIMEOUT`.
  The zombie/ephemeral agent's `analyze_and_execute` step now uses
  `timeout=EXECUTION_TIMEOUT` (env var, default 600s) and `max_retries=1` —
  verified in production that a failed attempt at this timeout rarely
  succeeds on retry with the same prompt/model, so retrying 3x just burns
  time.

## [1.13.17] - 2026-09-05

### Fixed
- **Orchestrator no longer treats every message as the answer to whatever's pending**
  — a message arriving while a plan or clarification is pending (e.g. a language
  complaint instead of an actual answer) used to get shoved into the pending slot
  verbatim, with zero verification, producing nonsense plans. Routing (new request?
  reply to a pending plan/clarification? just chat?) is now decided by the LLM's own
  reasoning turn via tool-calling (`abi_core.agent.routing_tools`), not a deterministic
  gate — sentinels (button clicks) and Guardian stay fully deterministic ahead of it.
  Includes a `ToolTracker`-based enforcement retry so a missed `create_plan` call
  doesn't silently degrade to the LLM writing the plan inline instead of delegating.
  Fixed along the way: reusing the LLM's own conversation memory (`thread_id=context_id`)
  across turns let a stale exchange from an earlier turn (with a different tool set
  bound) corrupt a later turn's tool-calling reliability — each reasoning turn now
  gets its own thread, since all cross-turn state already flows through explicit
  session context, not implicit LLM memory.
- **`@agent.tool()` functions never actually reached the LLM** — `AbiCore.run()` collected
  them into `agent_instance.extra_tools`, but nothing ever read that list, `self.agent`
  was already built (with an empty tool list) before `extra_tools` got populated, and
  registering ANY `@agent.tool()`/`@agent.step()` put the agent in DAG-only mode, which
  returns before the LLM's own tool-calling loop is ever reached. A tool declared
  without `depends_on` was also silently auto-executed on every single request as an
  unconditional DAG entry point — not just unreachable, actively wrong. Now: a tool WITH
  `depends_on` stays DAG-only (unchanged); one WITHOUT is excluded from the DAG and
  becomes LLM-callable instead, and `stream()`'s DAG path continues into an LLM turn
  (instead of returning immediately) when standalone tools are registered — zero
  behavior change for the agents that don't use this. Also fixed along the way:
  `StructuredTool.from_function(func=<async fn>)` silently never awaited async tools
  (the overwhelming majority of them), and `AgentResponse.error(msg, agent=...)` doesn't
  accept `agent=`, masking real DAG failures behind a `TypeError` instead.
- **Guardian never actually evaluated policies** — `evaluate_policy` and `format_decision`'s
  `input_map` referenced `$node.result.key`, but a node's output is stored raw, never
  wrapped in a `"result"` key (`tool_graph.py`) — `$node.result.key` was never valid
  syntax anywhere in this framework, and the same wrong pattern was documented as
  correct in the framework's own docstrings. The reference always failed to resolve,
  the node fails gracefully (not an exception) so it went unnoticed, and Guardian's
  actual OPA policy check silently never ran. Fixed in Guardian's real code, both
  scaffolding templates, and the framework's own misleading docstring examples.

### Changed
- **`abi_core.agent.llm_provider` rebuilt on `langchain.chat_models.init_chat_model()`**
  — replaces 8 hand-rolled per-provider constructor calls with LangChain's own
  actively-maintained universal dispatch. `temperature` no longer defaults to
  `0.1` on every request — it's optional and now defaults to `None` (omitted),
  matching what every current provider's own LangChain integration already
  defaults to (verified against langchain-anthropic 1.7.1, langchain-openai
  1.6.0, langchain-xai 1.3.0, langchain-aws 1.7.5). This was a real breaking
  bug: Claude's extended `thinking` mode rejects any explicit `temperature`
  other than 1, so forcing 0.1 broke every reasoning-enabled Claude call.
  This isn't limited to extended-`thinking` calls: Anthropic's own API docs
  confirm Claude 4.7+ (and Claude Mythos Preview) reject any non-default
  `temperature`/`top_p`/`top_k` unconditionally, full stop.
  New `extra_params` key on `LLM_CONFIG` forwards arbitrary kwargs straight
  to the underlying model constructor (`thinking`, `thinking_budget` /
  `thinking_level`, `max_tokens`, Azure's required `api_version`, etc.) — no
  framework code change needed for the next model generation's new
  parameter. Verified the values actually land on the constructed model
  (not just that construction doesn't error). `grok` now uses the native `langchain-xai` integration
  instead of the OpenAI-compatibility shim. `create_llm()`'s public
  signature (config dict in, `BaseChatModel` out) is unchanged — existing
  `LLM_CONFIG` dicts that set `temperature` explicitly keep working exactly
  as before. New optional extras: `anthropic`, `openai`, `gemini`, `grok`,
  `bedrock`, `vertex`, or all of them via `providers`.

### Added
- **`abi-core add chainlit`** — add a Chainlit chat UI **as a Docker service** for any
  agent with a web interface (not just the swarm). Wired into `compose.yaml` + the
  project network and started by `abi-core run` (no manual `chainlit run`); the target
  agent is auto-detected from `.abi/runtime.yaml` (Docker service name, not localhost),
  with a dynamic host port. It's a thin SSE client over `/stream` that opens a
  framework-managed session (token cached in `cl.user_session`, sent as
  `Authorization: Bearer`) so multi-turn stays coherent, and parses the stream safely
  (`json.loads` → `ast.literal_eval` fallback, never `eval`). Options: `--url`,
  `--title`, `--dir`.
- **Capability matching foundations (`abi_core.capabilities`)** — task-centric model
  selection (Phase 0; not yet wired into agents):
  - `CapabilityProfile` — a 7-dimension vector (`code_generation`, `tool_usage`,
    `reasoning`, `planning`, `structured_output`, `context_span`,
    `instruction_following`) shared by tasks and models. The 7th dimension captures
    that higher raw capability tends to reduce strict instruction compliance.
  - `TaskProfile` (what a task requires, with optional per-dimension weights) and
    `ModelProfile` (what a model provides, with provenance: `seed` vs `measured`,
    plus `with_observation()` to refine scores from executions).
  - `capability_gaps()`, `match_score()` (scalar ranking; penalizes deficit only —
    surplus capability doesn't reward), `select_model()` / `rank_models()`.
  - `seed_catalog()` — initial qualitative model profiles (`qwen3:latest`,
    `dolphin:70b`, `qwen3:latest/1.5b`) to bootstrap matching before measurement.
  - JSON load/save (`load_profiles`, `save_profiles`, `load_catalog`) — model
    profiling is a dev-time step: profile candidates, export JSON, load into the
    system, refine at runtime.
  - Visualization (`render_bars` for terminal, `render_radar_png` for a radar chart
    PNG via the optional `viz` extra / matplotlib).
  - Dev-time model profiler measuring **operational envelopes** (v2): per
    dimension, the highest complexity level a model sustains reliably (a
    staircase of code-verifiable leveled probes with **Wilson confidence
    intervals** and confirm-on-break; no LLM judge). Scores are absolute `[0,1]`
    envelopes (level/max), monotonic by construction. Leveled dimensions:
    `structured_output`, `reasoning`, `instruction_following`, `code_generation`;
    `tool_usage`/`planning`/`context_span` reported as unmeasured (need an
    execution sandbox). `abi-core capabilities profile <model> --output x.json`
    measures via Ollama and exports the profile.
  - CLI: `abi-core capabilities list|show [--radar out.png]|profile` to inspect
    and measure profiles.
  - Pure and testable; no agent integration yet.
- **Framework-managed sessions (`abi_core.session`)** — opt-in, LB/multi-pod safe
  session management for any ABI agent:
  - `SessionStore` with a **pluggable backend**: `InMemorySessionBackend` (default;
    per-pod, dev) and `RedisSessionBackend` (shared state via `redis.asyncio`, safe
    behind a load balancer). Select with `SESSION_BACKEND=memory|redis` — agent code
    doesn't change. Exported from `abi_core.agent`.
  - Opaque, **backend-generated** tokens (`abi_sess_<hex>`): the `context_id` is
    created server-side, never trusted from the client — fixes id spoofing and the
    shared `web-session` collision. `create_session` / `resolve` / `rotate` /
    `destroy`.
  - Conversation context (`get_context` / `update_context` / `clear_context`) is keyed
    by `context_id` and lives in the backend, not per-process RAM (survives pod hops
    with Redis).
  - Orchestrator web interface gains `/session/start`, `/session/rotate`,
    `/session/end`; `/stream` resolves an `Authorization: Bearer <token>` to its
    `context_id`. Without a token, an anonymous session is used
    (`ABI_SESSION_REQUIRED=true` to require one).
  - New env vars: `SESSION_BACKEND`, `SESSION_TTL`, `SESSION_REDIS_URL`
    (falls back to `REDIS_URL`), `ABI_SESSION_REQUIRED`.
  - All operations degrade gracefully when the backend is unavailable (never
    raise/block). See the "Sessions & Multi-turn" guide.
- **Built-in memory API (`abi_core.memory`)** — first-class short/long-term memory for
  any ABI agent, backed by the Agent Memory Server:
  - Write inside steps/tasks: `add_short_term_memory(topic, task, content, ...)`,
    `add_long_term_memory(...)` (also exported from `abi_core.agent`).
  - Read: `get_short_term_memory()`, `get_long_term_memory(query)`,
    `recall_memory_context(query)` (hydrates a system prompt).
  - LLM tools: `MEMORY_TOOLS` (`get_long_term_memory`, `get_short_term_memory`).
  - All operations degrade gracefully when the AMS is unavailable (never raise/block).
- **Agent Memory Server (AMS) in swarm scaffolding** — `abi-core create swarm` and the
  CLI generator (`add.py`) now provision two extra services for system-wide memory:
  - `<project>-redis-stack` — Redis 8 (bundles RediSearch/RedisJSON; required for the
    `HSETEX` command used by AMS) with `--appendonly yes` persistence.
  - `<project>-agent-memory` — `redislabs/agent-memory-server` exposing working
    (short-term) and long-term memory on port 8000.
  - The Builder injects `AGENT_MEMORY_URL=http://<project>-agent-memory:8000` into
    ephemeral agents so they can recall/store context.
  - AMS runs fully local via Ollama (LiteLLM): `GENERATION_MODEL`/`FAST_MODEL`/`SLOW_MODEL`
    = `ollama/qwen3:latest`, `EMBEDDING_MODEL` = `ollama/nomic-embed-text:v1.5` (768 dims).

### Fixed
- `AgentResponse.input_required(prompt, **kwargs)` — now accepts optional metadata
  (e.g. `status`, `questions`) preserved under `meta`. Previously raised
  `TypeError: unexpected keyword argument 'status'` when an agent emitted a
  clarification request, which broke the Planner → Orchestrator clarification flow.
- `A2AResponse.is_input_required` / `is_completed` / `is_failed` — now recognize
  protobuf `TaskState` values in all forms: integer (`"6"`), enum name
  (`TASK_STATE_INPUT_REQUIRED`), and legacy string (`input-required`). Previously
  only matched the legacy string, so clarification requests over a2a-sdk 1.0
  (protobuf, integer states) were never detected by the Orchestrator.
- **Semantic Layer agent discovery returned nothing (root cause)** — the `AgentCard`,
  `MeshItem` and `ToolRegistry` collections were created without a vector index config,
  so `near_vector` searches returned zero results even though objects carried valid
  vectors. Fixed by creating collections with
  `vector_config=Configure.Vectors.self_provided()` (bring-your-own-vector + HNSW index).
  Note: existing collections must be dropped once so they are recreated with the index.
- **Semantic store integrity** — agent cards could be indexed without an embedding
  vector (e.g. when the Semantic Layer started before Ollama could serve the model).
  Such vectorless objects exist but are invisible to `near_vector` search, so agent
  discovery silently failed and never recovered. Fixed with layered guards:
  - Startup waits until the embedding model can actually embed before indexing.
  - The store rejects any agent card with an empty/invalid vector (never persists
    dead state).
  - Startup idempotency is now by *validity*, not mere existence — a card present but
    vectorless is re-indexed instead of skipped forever.
  - `find_agent` self-heals on a miss by reconciling against disk (source of truth):
    it re-embeds and re-indexes missing cards, then retries. Already-valid cards are
    not reinserted.
  - `/health` returns `503 degraded` when the store has no vectorized cards, making
    the broken state visible.
  See the Troubleshooting guide → "Semantic Layer not finding agents".

### Breaking Changes
- **`AbiAgent` session methods are now `async`** — `get_session_context`,
  `process_answer`, and `clear_session` (plus the new `update_session_context`) are
  coroutines, because conversation context now lives in a pluggable session backend
  (in-memory or Redis) instead of a per-process `_conversation_history` dict. If you
  call them in a custom `stream()` override, add `await`:
  ```python
  # before
  context, was_answer = self.process_answer(context_id, query)
  # after
  context, was_answer = await self.process_answer(context_id, query)
  ```
  All are called from `async def stream(...)`, so this is a mechanical change. The
  `_conversation_history` attribute is gone.
- **`init_agent_card_store` parameter renamed** — `get_existing_uris_fn` →
  `get_valid_uris_fn`. The injected function must now return only URIs of cards stored
  **with a valid vector** (not mere existence), enforcing idempotency-by-validity. If
  you have a custom Semantic Layer `main.py`, update the keyword and provide a
  `get_valid_agent_card_uris()` that filters out vectorless objects.
- **a2a-sdk upgraded to 1.0+** — `AgentCard` is now protobuf (was pydantic). If you have a custom `config.py` that does `AgentCard(**data)`, replace it with:
  ```python
  from abi_core.common.agent_card_loader import load_agent_card
  card, meta = load_agent_card("path/to/card.json")
  ```
  The `meta` dict contains ABI-specific fields (`auth`, `id`, `supportedTasks`, `llmConfig`).
  Access URL via `card.supported_interfaces[0].url` or `get_agent_url(card)`.
- **Docker image stays on a2a-sdk 0.3.25** — existing projects running on the base image are unaffected. Only projects that install `abi-core-ai` directly from PyPI get the new SDK.

### Added
- `abi_core.common.agent_card_loader` — new module that separates A2A protocol fields from ABI metadata when loading agent cards
- `load_agent_card(path)` → returns `(AgentCard, abi_metadata_dict)`
- `build_agent_card(dict)` → same but from a dict instead of file
- `get_agent_url(card)` → extracts URL from `supported_interfaces[0]`

### Changed
- `a2a_server.py` — uses `create_jsonrpc_routes` + `create_agent_card_routes` (replaces removed `A2AStarletteApplication`)
- `agent_executor.py` — rewritten for protobuf types (`Part`, `TaskState.TASK_STATE_WORKING`)
- `abi_a2a.py` — uses `ClientFactory.connect()` and `Client.send_message()` (replaces `A2AClient`)
- `workflow.py` — updated event handling for new client response format
- `semantic_tools.py` — `tool_find_agent`/`tool_list_agents` use `build_agent_card()`
- All agent `config.py` files — use `load_agent_card()` instead of `AgentCard(**data)`
- CLI scaffolding templates updated for new pattern

### Added
- **AbiCore Application Runner**: FastAPI-style `agent = AbiCore()` with auto-config import
  - Auto-imports `config` and `AGENT_CARD` from the local `config` package
  - `agent.run(MyAgent())` starts the A2A server with zero boilerplate
  - Supports `web_interface_cls` and `interface_name` for web interfaces
- **Decorator-Based Task/Tool Registration**:
  - `@agent.step(name, depends_on, input_map)` — deterministic DAG step
  - `@agent.tool(name, depends_on, input_map)` — DAG step + LangChain tool for LLM
  - `@agent.mcp_tool(name, input_map)` — remote MCP tool via MCPToolkit with HMAC auth
  - `input_map` supports `$references` (e.g. `$clean_data.result`, `$input.query`)
  - Tasks/tools are wired into `ToolExecutionGraph` DAG automatically on `agent.run()`
- **AbiAgent Base Class Enhancements**:
  - Default `stream()` with SSE heartbeat (15s keepalive for CloudFront)
  - `self.tool_graph` — injected by AbiCore when decorators are used
  - `self.extra_tools` — LangChain tools from `@agent.tool()` decorators
  - `AgentResponse` typed responses: `.success()`, `.error()`, `.status()`, `.empty()`, `.input_required()`
- **LLM Provider**: `create_llm(llm_config)` supporting Ollama, OpenAI, Anthropic, Bedrock, Azure, Vertex AI, Grok
- **Agent Factory**: `agent_factory()` encapsulates all startup boilerplate (logging, web interface, A2A server)
- **Dual Transport Support for MCP Client**: Added support for both SSE and Streamable HTTP transports
  - `abi_core.abi_mcp.client.init_session()` now supports `transport='sse'` or `transport='streamable-http'`
  - SSE transport uses `/sse` endpoint (default, unidirectional streaming)
  - Streamable HTTP transport uses `/mcp` endpoint (bidirectional streaming)
  - Environment variable `MCP_TRANSPORT` for dynamic transport selection
  - Backward compatible - SSE remains the default transport
- **Transport Documentation**: Added comprehensive guide at `docs/user-guide/mcp-transports.md`
- **Transport Examples**: Added `examples/mcp_transport_examples.py` demonstrating both transports
- **Transport Tests**: Added unit tests for both transport protocols
- **Session Management Guide**: Added `docs/SESSION_MANAGEMENT.md` with best practices
  - Solutions for "Session terminated" errors
  - Proper session lifecycle management
  - Retry logic patterns
  - Connection pooling examples
  - Debugging and monitoring techniques
- **ToolExecutionGraph**: Deterministic tool execution graph built on LangGraph
  - DAG-based execution with topological ordering
  - `$-reference` resolution between nodes (e.g. `$input.user_query`, `$step1.result`)
  - Retry with exponential backoff per node
  - Checkpoint/resume on failures
  - Construction from JSON config or programmatic API
  - Dual execution mode: MCP tools (`tool` param) and local functions (`fn` param, sync or async)
  - `register_fn("name", callable)` for JSON-defined graphs with local functions
- **Automatic Agent Card Creation**: `abi-core add agent` now includes interactive skills session
  - Prompts for supported tasks/skills during agent creation
  - Generates signed agent card automatically
  - Saves card to agent directory and semantic layer (if exists)
  - Registers card in `runtime.yaml` and updates docker-compose
  - No need to run `add agent-card` separately

### Changed
- **MCP Client**: Enhanced `init_session()` to automatically select correct endpoint based on transport
- **Default MCP Transport**: Changed from `sse` to `streamable-http` across all components
  - Env var `MCP_TRANSPORT=sse` still works for override
- **Logging**: Migrated all `logger.*` calls to `abi_logging()` across the framework
- **Workflow Classes**: Renamed for clarity
  - `WorkflowGraph` → `AgentInteractionFlow` (backward-compatible aliases maintained)
  - `WorkflowNode` → `InteractionFlowNode`
  - `WorkflowState` → `InteractionFlowState`
- **ServerConfig**: Updated documentation to clarify supported transports ('sse' and 'streamable-http')
- **Utils**: Updated `get_mcp_server_config()` to support both transports via environment variables
- **Session Cleanup**: Improved resource cleanup in Streamable HTTP transport
  - Added explicit cleanup in finally blocks
  - Better logging for debugging session lifecycle
  - Prevents "Session terminated" errors from unclosed streams
- **MCPToolkit**: Enhanced error handling and added retry logic
  - Improved error handling with session-level error catching
  - Added `call_with_retry()` method for automatic retry on transient errors
  - Exponential backoff for retry attempts
  - Automatic detection of retryable errors (session terminated, connection issues)

### Fixed
- **Transport Validation**: Added proper validation for unsupported transport types
- **Streamable HTTP API**: Corrected implementation based on official MCP SDK documentation
  - `streamable_http_client` returns **3 elements**: `(read_stream, write_stream, connection_metadata)`
  - `sse_client` returns **2 elements**: `(read_stream, write_stream)`
  - Updated `init_session()` to properly unpack 3 elements for Streamable HTTP
  - Third element (connection metadata) is ignored with `_` placeholder
  - Reference: [MCP Python SDK README](https://github.com/modelcontextprotocol/python-sdk)
- **FastMCP API Update**: Updated all MCP server templates to use new FastMCP API
  - `FastMCP()` constructor no longer accepts `host` and `port` parameters
  - Host and port now passed to `mcp.run(transport=transport, host=host, port=port)`
  - Updated templates: `service_semantic_layer/layer/mcp_server/server.py.j2`
  - Updated scaffolding: `abi-cli/scaffolding/service_semantic_layer/layer/mcp_server/server.py.j2`
  - Updated testproject: `testproject/services/semantic_layer/layer/mcp_server/server.py`

## [1.5.8] - 2024-12-20

### Fixed
- **Version Synchronization**: Updated all version references to 1.5.8 for next PyPI release
- **Package Dependencies**: All requirements.txt files now correctly reference `abi-core-ai>=1.12.0`
- **Documentation**: Updated version references across all documentation files to 1.5.8

## [1.5.7] - 2024-12-20

### Fixed
- **Version Synchronization**: Updated all version references to match PyPI published version 1.5.7
- **Package Dependencies**: All requirements.txt files now correctly reference `abi-core-ai>=1.5.7`
- **Documentation**: Updated version references across all documentation files to 1.5.7

## [1.5.6] - 2024-12-20

### Added
- **AbiAgent Base Class**: Restored missing `abi_core.agent.agent.AbiAgent` base class
  - Fixed `ModuleNotFoundError: No module named 'abi_core.agent'` errors
  - Added proper abstract base class with `stream()` method
  - Includes lazy imports in `abi_core.__init__.py`
- **Semantic Module Exports**: Enhanced `abi_core.semantic` module exports
  - Added `validate_semantic_access` function export
  - Improved module structure for better accessibility

### Fixed
- **Import Dependencies**: Resolved missing module imports after monorepo migration
- **Template Consistency**: Updated all requirements.txt templates to use version 1.5.8
- **Documentation Version**: Updated Sphinx configuration to reflect current version

### Changed
- **Version Alignment**: All package requirements now point to `abi-core-ai>=1.12.0`
- **Documentation**: Updated version references across all documentation files

## [1.4.0] - 2024-12-16

### Added
- **Monorepo Modular Architecture**: Complete migration to modular package structure
  - `packages/abi-core/` - Core libraries (common/, security/, opa/, abi_mcp/)
  - `packages/abi-agents/` - Agent implementations (orchestrator/, planner/)
  - `packages/abi-services/` - Services (semantic-layer/, guardian/)
  - `packages/abi-cli/` - CLI and scaffolding tools
  - `packages/abi-framework/` - Umbrella package with unified API
  - Maintains full backward compatibility with existing imports
  - Symlinks ensure seamless transition during development
- **Enhanced Open WebUI Compatibility**: Improved web interface for agents
  - Fixed `Unclosed client session` errors in streaming responses
  - Corrected media types from `application/x-ndjson` to `text/plain`
  - Added proper `Connection: close` headers for Open WebUI
  - Fixed newline escaping in streaming responses (`\\n` → `\n`)
  - Enhanced CORS headers for better browser compatibility

### Changed
- **Project Structure**: Reorganized codebase into modular packages for better maintainability
- **Web Interface Templates**: Updated all agent web interfaces for Open WebUI compatibility
- **Import Paths**: Maintained backward compatibility while enabling new modular imports
- **Documentation**: Updated to reflect v1.5.2 architecture and features

### Fixed
- **Web Interface Streaming**: Resolved connection leaks in Open WebUI integration
- **Template Synchronization**: Ensured consistency between orchestrator and agent templates
- **URL Parsing**: Fixed malformed URLs in service communication
- **Connection Management**: Improved HTTP connection cleanup in streaming responses

### Technical Improvements
- **Modular Development**: Each package can be developed and tested independently
- **Community Collaboration**: Easier contribution workflow with focused packages
- **Deployment Flexibility**: Granular control over which components to deploy
- **Maintenance**: Simplified dependency management and version control

### Added
- **Agentic Orchestration Layer**: New `abi-core add agentic-orchestration-layer` command
  - Adds Planner Agent for task decomposition and agent assignment
  - Adds Orchestrator Agent for multi-agent workflow coordination
  - Automatic agent card generation with cryptographic signing
  - Agent cards include unique authentication tokens (HMAC-SHA256)
  - Cards automatically copied to semantic layer for discovery
  - Planner uses semantic search to find and assign agents
  - Orchestrator performs health checks with exponential backoff retries
  - Workflow execution with LangGraph state machine
  - Result synthesis using LLM for coherent output
  - Web interface for Orchestrator (HTTP/SSE endpoints)
  - Q&A flow between Planner and Orchestrator
  - Prerequisites validation (Guardian + Semantic Layer required)
  - Dynamic port assignment to avoid conflicts
- **Signed Agent Cards**: Agent cards now include authentication credentials
  - Generated at build time with `token_urlsafe(32)`
  - Include `@context`, `@type`, `id`, and `auth` fields
  - HMAC-SHA256 authentication method
  - Unique `key_id` and `shared_secret` per agent
  - Cards are immutable and signed during project setup
  - No runtime initialization needed
  - Semantic layer recognizes cards automatically
- **Model Provisioning Command**: New `abi-core provision-models` command for automated model management
  - Supports both centralized and distributed model serving modes
  - Automatically starts required Docker services (Ollama and agents)
  - Automatically downloads LLM and embedding models
  - Progress tracking and error handling
  - Updates runtime.yaml with provisioning status
  - Idempotent operation (skips already downloaded models)
  - In centralized mode: starts Ollama service automatically
  - In distributed mode: starts agent services (with Ollama) automatically
- **Always-Present Ollama Service**: Ollama service now included in all projects
  - Centralized mode: Single Ollama serves all agents
  - Distributed mode: Ollama serves embeddings, agents have own Ollama
  - Semantic layer always connects to main Ollama service
- **Advanced Guardian Security Service (Guardial)**: Complete security and policy enforcement system
  - Emergency response system with cryptographic signing
  - Real-time security dashboard (web interface)
  - Advanced alerting system with configurable thresholds
  - Comprehensive metrics collection and Prometheus integration
  - Audit persistence with retention policies
  - Secure policy engine with immutable core policies
  - OPA integration with healthchecks and auto-configuration
  - Domain-specific compliance (finance, healthcare)
  - Multi-layer policy evaluation (core + custom policies)
  - Risk scoring with contextual modifiers
- **Automatic Weaviate Integration**: Weaviate vector database now automatically added when using semantic layer
  - Automatically included when creating project with `--with-semantic-layer`
  - Automatically added when running `abi-core add semantic-layer`
  - Proper healthchecks and dependencies configured
  - Persistent volume for vector data
  - No manual configuration required
- **Model Serving Options**: New `--model-serving` flag for `create project` command
  - `centralized`: Single shared Ollama service for all agents (recommended for production)
  - `distributed`: Each agent has its own Ollama instance (default, current behavior)
- Centralized Ollama service template in `compose.yaml.j2` with healthcheck
- `model_serving` configuration field in `runtime.yaml` for persistent project settings
- Dynamic agent configuration in `add agent` command based on project's model serving mode
- Automatic detection and configuration of Ollama connectivity per agent
- Weaviate service tracking in `runtime.yaml` with configuration details

### Changed
- **Default LLM Model**: Changed from `llama3.2:3b` to `qwen3:latest` for better tool calling support
  - Excellent function/tool calling capabilities (required for agents)
  - Similar size (~2 GB)
  - Better performance for agent workflows
  - Strong reasoning and instruction following
  - Users can still specify any other model via `--model` flag
- `add agent` command now reads `model_serving` from `runtime.yaml` to configure agents appropriately
- Agent Docker Compose configuration adapts automatically to centralized/distributed mode
- Improved feedback messages showing which model serving mode is being used

### Removed
- **abi_mcp module**: Removed unused MCP client wrapper (not integrated in codebase)
- **agents_d directory**: Removed duplicate scripts (real scripts are in abi-image Docker base)

### Fixed
- Cleaned up unused code and duplicate files in package structure

## [1.0.0] - 2025-01-XX

### Added
- Initial beta release
- Project scaffolding with `create project` command
- Agent creation with `add agent` command
- Semantic layer service support
- Guardian security service support
- OPA policy integration
- A2A protocol support
- MCP server integration
- Docker Compose orchestration
- Agent cards for semantic discovery

### Documentation
- Comprehensive README with examples
- CLI command documentation
- Architecture overview
- Quick start guide

---

## Migration Guide

### Upgrading from 0.1.0b28 to 1.0.0

**No breaking changes** - All existing projects will continue to work as before.

#### New Projects

When creating new projects, you can now choose the model serving strategy:

```bash
# Centralized mode (recommended for production)
abi-core create project my-app --model-serving centralized

# Distributed mode (default, same as before)
abi-core create project my-app --model-serving distributed
# or simply
abi-core create project my-app
```

#### Existing Projects

Existing projects without `model_serving` in their `runtime.yaml` will automatically use `distributed` mode (current behavior). No changes needed.

To migrate an existing project to centralized mode:

1. Edit `.abi/runtime.yaml` and add:
   ```yaml
   project:
     # ... existing fields
     model_serving: "centralized"
   ```

2. Add the centralized Ollama service to your `compose.yaml`:
   ```yaml
   services:
     myproject-ollama:
       image: ollama/ollama:latest
       container_name: myproject-ollama
       ports:
         - "11434:11434"
       volumes:
         - ollama_data:/root/.ollama
       environment:
         - OLLAMA_HOST=0.0.0.0
       networks:
         - myproject-network
       restart: unless-stopped
   
   volumes:
     ollama_data:
       driver: local
   ```

3. Update existing agents to use the centralized service (optional, but recommended):
   - Remove individual Ollama ports (e.g., `11435:11434`)
   - Change `OLLAMA_HOST` to `http://myproject-ollama:11434`
   - Set `START_OLLAMA=false` and `LOAD_MODELS=false`
   - Add `depends_on: [myproject-ollama]`
   - Remove individual `ollama_data` volumes

---

## Model Serving Comparison

| Feature | Centralized | Distributed |
|---------|-------------|-------------|
| Ollama instances | 1 shared | 1 per agent |
| Resource usage | Lower | Higher |
| Model management | Centralized | Per-agent |
| Isolation | Shared | Complete |
| Recommended for | Production | Development |
| Port conflicts | None | Possible |
| Startup time | Faster (agents) | Slower |

---

**Note**: Guardian service always maintains its own Ollama instance for security isolation, regardless of the chosen mode.
