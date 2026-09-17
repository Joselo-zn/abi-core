# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`AgentResponse.element(element_type, props, name)`** — agents can now
  send rich elements (image/file/pdf/audio/video/text/dataframe/qr) alongside
  their response, rendered inline by a Chainlit-based UI. Binary content
  should ride as a `url` (e.g. from `ArtifactStore.get_url()`) rather than
  inline bytes. `element_type="qr"` renders a QR server-side from a
  `data` string (URL, typically) — agents never need the `qrcode` package
  themselves, only the rendering process does (new `qrcode[pil]` dependency,
  `ui` extra only). See `.abi/specs/agent-rich-elements.md` and
  [Rich Elements](docs/single-agent/10-rich-elements.md).
- **Custom `.jsx` elements**, bundled and auto-installed. `abi_core.ui.chainlit_app`
  now ships `InfoCard` and `MapEmbed` as reference components and copies
  them into `public/elements/` on import — no per-project Dockerfile step
  needed, same "no project needs its own copy" principle the module already
  followed. Any `element_type` that isn't a built-in type is treated as a
  custom element name. See `.abi/specs/agent-custom-elements.md`.
- **Orchestrator "recent error" awareness** — the last error recorded for a
  session (`AbiAgent.record_error`) now surfaces once, as
  `recent_error_summary` in the reasoning turn's routing contract, on the
  very next request in that session, then is consumed (cleared) — no TTL,
  no timestamp; it shows up exactly once, never repeats. See
  `.abi/specs/orchestrator-last-error-awareness.md`.
- The Orchestrator's per-task chat step now shows an actual QR + download
  link for generated artifacts, using the two features above together.
- **`write_pdf` fixed tool + `direct_tool` plan tasks** — fixes the Planner
  getting stuck in an infinite clarification loop when asked for a PDF
  deliverable (it could only recognize "write a file" tasks, and its own
  rules forbade any task that executes code, with no fallback). Rather than
  loosening that rule (rejected — it would let the Planner ask an ephemeral
  agent to generate-and-run code, reopening a prompt-injection surface), a
  `PlanTask` can now carry `direct_tool: "write_pdf"`: a fixed, audited
  tool (`abi_core.common.library_tools.write_pdf`, via `fpdf2`) that the
  **Planner itself** executes directly — no ephemeral agent, no Builder
  round-trip — then uploads to MinIO and reports the link, same as an
  ephemeral agent's own flow. It still goes through the same plan
  confirmation (approve/reject/modify) as any other task. See
  `.abi/specs/planner-direct-tool-pdf.md`.
- **`AbiAgent.record_conversation_turn` / `format_conversation_summary`** —
  fixes a context-loss bug where a plain conversational turn (e.g. "I'm in
  Xilitla, staying 3 days") was completely forgotten by the very next
  request ("make me an itinerary"), forcing the Orchestrator to re-ask for
  details the user had just given. Root cause: nothing outside
  `pending_plan`/`pending_clarification` was ever persisted across turns —
  `_reasoning_turn`'s only discretionary memory path (`MEMORY_TOOLS`
  tool-calling) is separately documented as broken
  (`.abi/issues/2026-09-09-fase1-memory-tools-lento.md`). Every resolved
  turn is now deterministically appended to a rolling session window
  (`session_backend`, LB/multi-pod safe — the Orchestrator also switched
  from the in-memory session backend to Redis, `SESSION_BACKEND=redis`,
  fixing the same restart-loses-everything exposure for `pending_plan`/
  `last_error` as a side effect); the oldest turn is promoted to AMS
  long-term memory before being dropped once the window (`CONVERSATION_WINDOW`,
  default 5) overflows. Generic capability, lives in `AbiAgent`/`AbiCore`
  per `WORKING_RULES.md` → *Perspectiva Local vs Global*, not swarm-specific.
  Getting the data into the prompt wasn't sufficient on its own — the
  routing decision's LLM call had no system prompt at all, so it kept
  pattern-matching only the literal current message; a targeted
  `SystemMessage` explaining *why* the recent-conversation block matters
  fixed that. See `.abi/specs/orchestrator-conversation-memory.md`.

### Changed
- **`record_error`/`record_pending_plan`/`clear_pending_plan` moved from
  Orchestrator-private methods to `AbiAgent` (generic, inherited by any
  agent) with matching `AbiCore` passthroughs** — same pattern already used
  for `get_session_context`/`update_session_context`. The Orchestrator's
  swarm-specific piece (persisting a plan's methodology to AMS) stays local,
  renamed `_record_plan_methodology`, now called alongside the inherited
  `record_pending_plan`. No behavior change — pure relocation/delegation.
  See `.abi/specs/agent-session-bookkeeping-methods.md`.
- **`AbiAgent._run_with_heartbeat()`/`_run_llm_turn()` are now async
  generators** that yield each heartbeat live as it occurs, ending with a
  `_HeartbeatDone(result)` sentinel — not a batched list handed back after
  the wait finishes, which defeated the point of a heartbeat (see Fixed,
  below). `max_wait` is `Optional[float] = None` — no default cap. Guessing
  one global timeout for every call site was the actual bug (measured live:
  the same call site, same code path, needed 164s one run and 179s — timed
  out — the next); *coro* is now expected to bound its own real work
  internally (a DAG step's own `timeout`, a subprocess's own `timeout=`, an
  LLM call's own bound) instead. `max_wait` remains available as an opt-in
  safety net for a specific coroutine known not to self-bound yet
  (`HeartbeatTimeoutError`, no longer needs to carry `.heartbeats` — nothing
  is generated before a cutoff that wasn't already streamed live). All 9
  call sites, the scaffolding template used by `abi-core add service
  guardian`, and downstream example projects updated to the new
  `async for item: isinstance(item, _HeartbeatDone)` pattern. Breaking for
  any subclass calling `_run_with_heartbeat` directly with the old
  `await ... -> (result, heartbeats)` shape. See
  `.abi/specs/heartbeat-timeout-redesign.md` ("Revisión 2026-09-11").
- Chainlit UI (`abi_core.ui.chainlit_app`): the single "Working" step is now
  a "Processing" parent with one child step opened per plan task
  (`meta.task_key`/`task_label`), so each task stays visible in the chat
  instead of being overwritten by the next one. The parent step's name
  reflects the active agent while no task is running yet (routing/planning/
  synthesis) instead of staying fixed. See
  `.abi/specs/chainlit-active-agent-label.md`,
  `.abi/specs/chainlit-per-step-ui.md`.

### Fixed
- **`container_runtime.py`'s Docker SDK calls had no timeout of their own**
  — the only real I/O in the framework without one (`run_shell`'s
  `subprocess.run(timeout=60)` already kills its child process for real;
  Docker's sync SDK, dispatched via `asyncio.to_thread`, had nothing).
  `run_container`/`destroy_container` now wrap those calls in
  `asyncio.wait_for` (300s for `containers.run`, which may need to pull the
  image; 30s for `get`/`remove`). Documented explicitly that this bounds the
  *wait*, not the thread itself — asyncio cancellation is cooperative and
  can't force-stop a thread already running a blocking Docker SDK call. See
  `.abi/specs/heartbeat-timeout-redesign.md`.
- **Heartbeat progress was never actually live.** `_run_with_heartbeat`
  batched every `AgentResponse.status(...)` into a list only handed back
  once the wait was over — the whole point of a heartbeat (keeping an SSE
  connection alive under a proxy's idle timeout, see `_HEARTBEAT_INTERVAL`'s
  own comment) was defeated for any call taking longer than that timeout.
  Fixed as part of the generator rewrite above — heartbeats now reach the
  client the instant they occur. See `.abi/specs/heartbeat-timeout-redesign.md`.
- **Artifact download links (and QR codes of them) used an internal
  Docker-network hostname the user's browser can't resolve.**
  `ArtifactStore` used one `endpoint` for both internal I/O and the
  presigned URLs handed to a human. New `ARTIFACT_PUBLIC_ENDPOINT` (falls
  back to `ARTIFACT_ENDPOINT` when unset) is used only for the latter.
  Verified empirically that MinIO's Console UI port (9001, `/browser/...`)
  does *not* validate presigned URLs — it just serves the Console's own app
  shell — so this must point at the actual S3 API port (9000-style), not
  the Console. See [Artifact Store](docs/production/05-artifact-store.md).

### Removed
- **`abi-core add abi-swarm`, `abi-core create swarm`, `abi-core remove abi-swarm`** —
  the combined Orchestrator+Planner+Builder scaffolding graduated into its own
  product (ABI Swarm), built and maintained separately from this framework now
  that it's earned enough standalone value. The reference agent implementations
  themselves (`abi_agents.planner`/`.orchestrator`/`.builder`) are untouched —
  still the canonical example for `depends_on`, plan confirmation, methodology
  selection, and ephemeral agent creation (see
  [Planner & Orchestrator](docs/orchestration/01-planner-orchestrator.md)).
  Replicating the combined system is now a manual wiring exercise (`abi-core
  create project` + `abi-core add agent`/`add service` for each piece), not a
  single command. See `.abi/specs/remove-abi-swarm-cli-scaffolding.md`.

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
  Planner's `parse_plan` on the malformed result). See
  `.abi/specs/orchestrator-unified-routing-contract.md`.
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
  decision. See `.abi/tsd/2026-09-09-routing-decision-model-profiling.md`.
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
  remain on security-fix-only maintenance upstream. See
  `.abi/tsd/2026-09-10-dependency-upgrade-audit.md`.

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
  matching the other 4 services. See
  `.abi/tsd/2026-09-09-routing-decision-model-profiling.md`.

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
  artifact-extraction code right below it. See
  `.abi/tsd/2026-09-06-leak-protobuf-crudo-sse.md`.
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
  time. See `.abi/tsd/2026-09-06-timeout-por-step-dag.md`.

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
  session context, not implicit LLM memory. See
  `.abi/tsd/2026-08-23-orchestrator-tool-call-routing.md`.
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
  accept `agent=`, masking real DAG failures behind a `TypeError` instead. See
  `.abi/tsd/2026-08-23-agent-tool-dag-llm-coexist.md`.
- **Guardian never actually evaluated policies** — `evaluate_policy` and `format_decision`'s
  `input_map` referenced `$node.result.key`, but a node's output is stored raw, never
  wrapped in a `"result"` key (`tool_graph.py`) — `$node.result.key` was never valid
  syntax anywhere in this framework, and the same wrong pattern was documented as
  correct in the framework's own docstrings. The reference always failed to resolve,
  the node fails gracefully (not an exception) so it went unnoticed, and Guardian's
  actual OPA policy check silently never ran. Fixed in Guardian's real code, both
  scaffolding templates, and the framework's own misleading docstring examples. See
  `.abi/tsd/2026-08-23-guardian-input-map-result-bug.md`.

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
  `bedrock`, `vertex`, or all of them via `providers`. See
  `.abi/tsd/2026-09-04-llm-provider-redesign.md`.

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
  - Pure and testable; no agent integration yet. See
    `.abi/specs/capability-matching.md` and
    `.abi/specs/capability-profiling-methodology.md`.
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
