"""
LLM Provider — Unified factory for creating LangChain chat models.

Built on ``langchain.chat_models.init_chat_model()`` — LangChain's own
actively-maintained universal provider dispatch + kwarg passthrough — instead
of hand-rolling a direct constructor call per provider. The old design forced
``temperature`` to a float (0.1 default) on every single call and needed a
framework code change for every new provider-specific parameter. That broke
down as models evolved: **as of Claude 4.7 and later (and Claude Mythos
Preview), Anthropic's own Messages API no longer supports ``temperature``,
``top_p``, or ``top_k`` at all — sending any non-default value returns an
HTTP 400** (confirmed directly against Anthropic's current API docs,
platform.claude.com/docs/en/build-with-claude/working-with-messages: "Omit
them from request payloads and use prompting to guide the model's behavior
instead"). This isn't limited to extended-``thinking`` calls — it's
unconditional for the whole 4.7+ model family. Gemini's reasoning knob is
``thinking_budget`` on 2.5 models and ``thinking_level`` on 3+. Every current
provider's own LangChain integration already defaults ``temperature`` to
``None`` (verified against the installed langchain-anthropic 1.7.1,
langchain-openai 1.6.0, langchain-xai 1.3.0, langchain-aws 1.7.5) — this
module now follows that lead instead of fighting it. See
.abi/tsd/2026-09-04-llm-provider-redesign.md for the full investigation.

Supports three scenarios:
1. Cloud managed: Bedrock, Azure OpenAI, Vertex AI
2. Self-hosted: Ollama (local or remote)
3. Direct APIs: OpenAI, Anthropic, Google Gemini, Grok (xAI, native
   langchain-xai integration — no longer the OpenAI-compatibility shim)

All provider integration packages are imported lazily (via init_chat_model)
to avoid forcing unnecessary dependencies — only langchain-ollama is a hard
dependency of this package; everything else is pip-installed by whoever
actually uses that provider.

Usage — same shape as before, still just a config dict in, BaseChatModel out:

    from abi_core.agent.llm_provider import create_llm

    llm = create_llm({
        "provider": "ollama",
        "model": "qwen3:latest",
        "temperature": 0.1,
        "base_url": "http://localhost:11434",
    })

``temperature`` is now optional — omit it (or leave it ``None``) to let the
provider use its own default, which current providers already default to
``None`` themselves (Gemini defaults to 0.7 instead — still fine to omit).
Use ``extra_params`` for anything provider- or model-generation-specific that
isn't one of the common keys below — passed straight through to the
underlying LangChain chat model constructor, so a new reasoning parameter
never needs a framework code change again:

    llm = create_llm({
        "provider": "anthropic",
        "model": "claude-opus-4-6-20260115",
        "extra_params": {
            "thinking": {"type": "enabled", "budget_tokens": 4000},
        },
    })
"""

import asyncio
import json
import os
from typing import Any, Dict, Optional


def _extract_text(content: Any) -> str:
    """Normalize a LangChain message's `.content` to plain text.

    ChatOllama always returns a plain `str`. ChatGoogleGenerativeAI (Gemini)
    doesn't — verified live: the same Path A call returned `.content` as a
    `list` of content blocks instead, breaking every caller downstream that
    assumed `invoke()`'s return value supports `.strip()` (the Planner's
    methodology selection and `parse_plan`, both — reproduced with
    `'list' object has no attribute 'strip'` immediately after switching
    `LLM_PROVIDER` from ollama to gemini, no other change). `invoke()`'s own
    docstring promises "the text content of the LLM response" regardless of
    provider — this is what actually keeps that promise instead of leaking
    a provider-specific shape to every caller.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
        return "".join(parts)
    return str(content)

from abi_core.common.utils import abi_logging

# Our provider names -> (langchain's model_provider identifier, package to
# suggest installing if it's missing). See init_chat_model's own docstring
# for the full canonical list this is drawn from.
_PROVIDER_MAP = {
    "ollama": ("ollama", "langchain-ollama"),
    "openai": ("openai", "langchain-openai"),
    "anthropic": ("anthropic", "langchain-anthropic"),
    "gemini": ("google_genai", "langchain-google-genai"),
    "grok": ("xai", "langchain-xai"),
    "bedrock": ("bedrock_converse", "langchain-aws"),
    "azure": ("azure_openai", "langchain-openai"),
    "vertex": ("google_vertexai", "langchain-google-vertexai"),
}


def parse_extra_params(raw: Optional[str], var: str = "LLM_EXTRA_PARAMS") -> Dict[str, Any]:
    """Parse a JSON object of LangChain constructor kwargs from an env var.
    Empty or unset: ``{}``. Invalid JSON, or JSON that is not an object,
    raises ``ValueError`` naming the variable, so a bad value fails at
    start-up instead of at the first model call."""
    if raw is None or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"{var} is not valid JSON: {e}") from e
    if not isinstance(value, dict):
        raise ValueError(f"{var} must be a JSON object, got {type(value).__name__}")
    return value


def llm_config_from_env(
    *,
    model_env: str = "MODEL_NAME",
    default_model: str = "qwen3:latest",
    default_ollama_host: str = "http://localhost:11434",
    ollama_extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an ``LLM_CONFIG`` for ``create_llm`` from the environment —
    the one place every agent's config reads it from, so a parameter set
    in the deployment reaches LangChain.

    - ``LLM_PROVIDER`` (default ``ollama``), the model from ``model_env``.
    - ``LLM_TEMPERATURE``: omitted unless set (Claude 4.7+ rejects any).
    - ``LLM_BASE_URL``; without it, ``OLLAMA_HOST`` only for Ollama — a
      hosted provider gets no base_url rather than the Ollama server's.
    - ``LLM_API_KEY`` and the cloud keys (``AWS_REGION``,
      ``AZURE_DEPLOYMENT``, ``AZURE_ENDPOINT``, ``VERTEX_PROJECT``,
      ``VERTEX_LOCATION``); ``create_llm`` uses only its provider's.
    - ``extra_params``: ``ollama_extra_params`` (Ollama only), then
      ``LLM_EXTRA_PARAMS`` (a JSON object) over them — the environment wins.

    An empty variable counts as unset (compose passes unset vars as "").
    See .abi/specs/implemented/llm-params-from-config.md.
    """
    def env(name: str) -> Optional[str]:
        value = os.getenv(name)
        return value if value not in (None, "") else None

    provider = (env("LLM_PROVIDER") or "ollama").strip().lower()
    temperature = env("LLM_TEMPERATURE")
    base_url = env("LLM_BASE_URL")
    if base_url is None and provider == "ollama":
        base_url = env("OLLAMA_HOST") or default_ollama_host

    extra = dict(ollama_extra_params or {}) if provider == "ollama" else {}
    extra.update(parse_extra_params(os.getenv("LLM_EXTRA_PARAMS")))

    return {
        "provider": provider,
        "model": env(model_env) or default_model,
        "temperature": float(temperature) if temperature is not None else None,
        "base_url": base_url,
        "api_key": env("LLM_API_KEY") or "",
        "aws_region": env("AWS_REGION") or "us-east-1",
        "azure_deployment": env("AZURE_DEPLOYMENT") or "",
        "azure_endpoint": env("AZURE_ENDPOINT") or "",
        "vertex_project": env("VERTEX_PROJECT") or "",
        "vertex_location": env("VERTEX_LOCATION") or "us-central1",
        "extra_params": extra,
    }


def create_llm(llm_config: Dict[str, Any]):
    """
    Create a LangChain BaseChatModel from a config dictionary.

    Required keys:
        provider: str — one of: ollama, openai, anthropic, gemini, grok,
                        bedrock, azure, vertex
        model: str — model name/id

    Common optional keys:
        temperature: float | None — omitted (or ``None``, the default) lets
            the provider use its own default. Claude 4.7+ (and Claude Mythos
            Preview) REJECT any non-default `temperature`/`top_p`/`top_k`
            outright (HTTP 400) — not just with extended thinking, always.
            If you have an older config that sets this explicitly and you
            move to a 4.7+ model, remove the key rather than relying on a
            "safe" value; there isn't one anymore.
        api_key: str (for API-based providers — falls back to each
            provider's own standard env var, e.g. ANTHROPIC_API_KEY, if unset)
        base_url: str — custom/self-hosted endpoint. Required in practice
            for ollama (defaults to http://localhost:11434 if omitted);
            optional override for every other provider.
        extra_params: dict — forwarded as-is to the underlying LangChain
            chat model constructor. Use this for anything provider- or
            model-generation-specific: `thinking`, `thinking_budget`,
            `thinking_level`, `max_tokens`, `top_p`, `reasoning_effort`,
            `api_version` (azure), etc. — whatever this model needs that
            isn't one of the keys above. See the provider's own LangChain
            integration reference for the exact field names it accepts:
            https://reference.langchain.com/python/integrations/

    Cloud-specific keys:
        aws_region: str (bedrock) — passed through as region_name
        azure_deployment: str (azure)
        azure_endpoint: str (azure)
        vertex_project: str (vertex) — passed through as project
        vertex_location: str (vertex) — passed through as location

    Azure gotcha (verified against the installed AzureChatOpenAI): it
    ALWAYS requires an api version — either the OPENAI_API_VERSION env var,
    or extra_params={"api_version": "2024-10-01"} (or whatever date your
    deployment needs). Construction raises a clear pydantic ValidationError
    if neither is set — this module doesn't default one for you, since the
    correct value depends entirely on your Azure deployment.

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        ValueError: If provider is unknown, or its integration package
            isn't installed (surfaced with an actionable pip-install message).
    """
    provider = llm_config.get("provider", "ollama").lower().strip()
    model = llm_config.get("model", "qwen3:latest")

    if provider not in _PROVIDER_MAP:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Supported: {', '.join(_PROVIDER_MAP)}"
        )
    model_provider, package = _PROVIDER_MAP[provider]

    # extra_params first so the explicit common keys below can't be
    # silently shadowed by a stray entry in there.
    kwargs: Dict[str, Any] = dict(llm_config.get("extra_params") or {})

    temperature = llm_config.get("temperature")
    if temperature is not None:
        kwargs["temperature"] = float(temperature)

    api_key = llm_config.get("api_key")
    if api_key:
        kwargs["api_key"] = api_key

    # `base_url` is a real field (or alias) on every provider's LangChain
    # integration class — verified directly against the installed packages,
    # not assumed. Ollama is the one provider where omitting it entirely
    # isn't viable (self-hosted, no server-side default makes sense).
    base_url = llm_config.get("base_url")
    if provider == "ollama":
        kwargs["base_url"] = base_url or "http://localhost:11434"
    elif base_url:
        kwargs["base_url"] = base_url

    if provider == "bedrock":
        kwargs.setdefault("region_name", llm_config.get("aws_region", "us-east-1"))
    elif provider == "azure":
        kwargs.setdefault("azure_deployment", llm_config.get("azure_deployment", model))
        endpoint = llm_config.get("azure_endpoint")
        if endpoint:
            kwargs.setdefault("azure_endpoint", endpoint)
    elif provider == "vertex":
        kwargs.setdefault("location", llm_config.get("vertex_location", "us-central1"))
        project = llm_config.get("vertex_project")
        if project:
            kwargs.setdefault("project", project)

    abi_logging(f"[🤖] Creating LLM: provider={provider}, model={model}")

    from langchain.chat_models import init_chat_model

    try:
        llm = init_chat_model(model, model_provider=model_provider, **kwargs)
    except ImportError as e:
        raise ValueError(
            f"{package} is required for provider '{provider}'. pip install {package}"
        ) from e

    abi_logging(f"[✅] {provider.capitalize()} LLM ready: {model}")
    return llm


async def _stream_agent_with_timeout(agent_instance, inputs: dict, config: dict, chunk_timeout: float):
    """Consume `agent.astream()` bounding EACH chunk's wait, instead of a
    bare `async for` — same pattern as `abi_a2a.py::agent_connection()`'s
    InactivityWatchdog. A single `asyncio.wait_for()` around the WHOLE
    call can't recover if the underlying model call never yields control
    back to the event loop (see Path A's own timeout comment below) — the
    cancellation itself never completes. Bounding each chunk means a
    genuinely stalled stream surfaces as a clear TimeoutError within
    `chunk_timeout` seconds, and — just as important — leaves the event
    loop free between chunks for the step's own heartbeat to actually run.
    Reproduced live 2026-09-29: two ephemerals running this exact path
    concurrently produced zero heartbeat ticks over a full 600s step
    timeout — the event loop was blocked solid, not just slow.

    `stream_mode="messages"`, not `"updates"` — confirmed live 2026-10-01
    this distinction is the whole point, not a style choice. `"updates"`
    only yields once a full graph node (e.g. the entire LLM call) finishes,
    so a single generation that legitimately takes longer than
    `chunk_timeout` (measured live: ~6.5 tok/s on CPU-only Ollama, a few
    hundred tokens easily exceeds 120s) produced ZERO chunks the whole time
    and got killed as "stalled" while `llama-server`'s own log showed it
    steadily generating the entire way through — a false positive that then
    discarded all that real progress on retry. `"messages"` yields a
    `(message_chunk, metadata)` tuple per token (confirmed against the
    installed langgraph==1.2.12: hundreds of chunks over the same call,
    not one), so `chunk_timeout` now measures actual token-level
    inactivity, not graph-step duration. See .abi/specs/not-implemented/
    stream-mode-updates-false-stall-detection.md.

    The FIRST chunk gets no `chunk_timeout` — confirmed live 2026-10-01:
    with Ollama's single generation slot (`-np 1`) genuinely free, time to
    first chunk was 10.3s, but a request queued behind another real
    generation can legitimately wait as long as that other generation
    takes (observed: 20+ minutes for a long file) before the slot frees up
    at all — zero chunks the whole time, same as queueing in any
    single-server system. That's a legitimate wait, not inactivity (same
    "no importa que tarde" tradeoff already accepted for the outer
    `node.timeout` backstop), so it isn't bounded here — the outer
    `ToolGraphNode.timeout` backstop still covers "this request never gets
    a turn at all". Only once streaming has genuinely begun does a gap
    become suspicious enough to bound with `chunk_timeout`.

    Raises `asyncio.TimeoutError` if a token stops arriving mid-stream
    (never for the wait before the first one).
    """
    final = ""
    stream_iter = agent_instance.astream(inputs, config=config, stream_mode="messages").__aiter__()
    first_chunk = True
    while True:
        try:
            if first_chunk:
                chunk, _metadata = await stream_iter.__anext__()
                first_chunk = False
            else:
                chunk, _metadata = await asyncio.wait_for(stream_iter.__anext__(), timeout=chunk_timeout)
        except StopAsyncIteration:
            break
        msg_type = type(chunk).__name__
        content = getattr(chunk, "content", "")
        # Confirmed live: a tool's result streams as a plain `ToolMessage`
        # (not `ToolMessageChunk`) even under stream_mode="messages" — must
        # still be excluded from the accumulated final text, same as before.
        if content and msg_type != "ToolMessage":
            # Gemini streams content as a list of blocks, not a string —
            # live 2026-10-10 every code agent crashed here on its final turn.
            final += _extract_text(content)
    return final


async def invoke(
    llm_config: Dict[str, Any],
    prompt: str,
    tools: list = None,
    thread_id: str = None,
    system_prompt: str = None,
    required_tools: list = None,
    call_timeout: float = None,
    recursion_limit: int = None,
    checkpointer: Any = None,
) -> str:
    """Unified LLM invocation with optional tool enforcement.

    recursion_limit: max LangGraph steps for the tool-calling agent (Path
    B). Each tool call costs two steps (model turn + tool node). Default 10
    — enough for a one-file task, a guard against endless tool loops. A
    caller whose task needs more calls (e.g. the integration reviewer:
    read 5 files + write 5) must pass a budget sized to the work.

    Args:
        llm_config: Provider config dict for create_llm().
        prompt: The user/system message to send.
        tools: Optional list of LangChain tools.
        thread_id: Key of the tool-calling conversation (Path B) in
            ``checkpointer``. On its own it keeps nothing between calls:
            without a ``checkpointer`` each call gets a fresh
            ``MemorySaver``, and a call without tools (Path A) ignores it.
            For memory across requests, use ``checkpointer`` with the same
            ``thread_id``, or the agent memory API
            (``abi_core.memory``).
        system_prompt: Optional system instructions.
        required_tools: List of tool names that MUST be called.
            If declared, the framework enforces usage with retry + fallback.
        call_timeout: Optional seconds to bound a single no-tools call
            (Path A only — see below). ``None`` (default) imposes no cap,
            same as everywhere else in this framework — pass it explicitly
            only for a call site proven to need it. See "Path A timeout"
            below for why this exists at all.
        checkpointer: Optional LangGraph checkpointer for the tool-calling
            agent (Path B), used with ``thread_id``. Default: a fresh
            ``MemorySaver`` per call, so the conversation ends with the call.
            Pass one that outlives the call to read the conversation back
            later (a code agent answering the reviewer about what it did).

    Returns:
        The text content of the LLM response.
    """
    llm = create_llm(llm_config)

    # ── Path A: LLM only (no tools) ────────────────────────────
    if not tools:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Path A timeout (opt-in via call_timeout, same "prove it's needed
        # per call site" rule as _run_with_heartbeat's max_wait — see
        # .abi/specs/heartbeat-timeout-redesign.md). Added after a live,
        # reproduced-twice hang: the Orchestrator's synthesis call sent
        # right after a long ephemeral-agent generation just finished on
        # the same (CPU-only, single-instance) Ollama got stuck
        # indefinitely — TCP connection ESTABLISHED, zero bytes queued
        # either direction, Ollama's own container at 0% CPU (not
        # computing, just wedged).
        #
        # First version of this fix wrapped `llm.ainvoke(messages)`
        # directly in asyncio.wait_for() — verified live that it does NOT
        # work: 27+ minutes elapsed on a real hang with no timeout ever
        # firing. Root cause: asyncio.wait_for() only returns once the
        # cancellation of the wrapped awaitable actually completes — which
        # requires that awaitable to reach an await checkpoint and raise
        # CancelledError. If it's stuck inside a genuinely blocking call
        # that never yields control back to the event loop (suspected
        # inside ollama.AsyncClient/httpx, not confirmed further), that
        # checkpoint never comes, cancellation never completes, and
        # wait_for hangs right along with it — same failure mode one level
        # deeper, not a fix.
        #
        # Using asyncio.to_thread(llm.invoke, ...) (the SYNC method, in a
        # real OS thread) instead of awaiting `.ainvoke()` directly sidesteps
        # this: cancelling the asyncio-side wrapper around a to_thread
        # future can complete without the underlying thread cooperating or
        # ever finishing — same pattern already proven for Docker SDK calls
        # in container_runtime.py ("Cancelling the underlying task is a
        # cooperative request, not a guarantee... that work keeps running
        # in the background regardless"). One retry with a brand-new client
        # before giving up. See .abi/specs/llm-call-timeout-ollama-stall.md.
        if call_timeout is None:
            response = await llm.ainvoke(messages)
        else:
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(llm.invoke, messages), timeout=call_timeout
                )
            except asyncio.TimeoutError:
                abi_logging(
                    f"[⚠️] LLM call timed out after {call_timeout}s — retrying once "
                    "with a fresh client",
                    level="warning",
                )
                retry_llm = create_llm(llm_config)
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(retry_llm.invoke, messages), timeout=call_timeout
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(
                        f"LLM call timed out twice ({call_timeout}s each) — "
                        "the model server appears stuck, not just slow."
                    )
        return _extract_text(response.content) if hasattr(response, "content") else str(response)

    # ── Path B: Agent with tools ────────────────────────────────
    from langchain.agents import create_agent
    from abi_core.common.tool_enforcement import ToolTracker, get_enforcement_system_prompt

    # Setup enforcement if required_tools declared
    tracker = None
    actual_tools = tools
    enforced_system_prompt = system_prompt or ""

    if required_tools:
        tracker = ToolTracker(tools, required_tools)
        actual_tools = tracker.wrapped_tools
        enforced_system_prompt += get_enforcement_system_prompt(required_tools)

    if checkpointer is not None and not thread_id:
        raise ValueError("invoke(checkpointer=...) needs a thread_id")
    if checkpointer is None and thread_id:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    agent = create_agent(
        model=llm,
        tools=actual_tools,
        system_prompt=enforced_system_prompt,
        checkpointer=checkpointer,
    )
    abi_logging(f'CREATE AGENT CALLED WITH TOOLS {[t.name for t in actual_tools]}')
    inputs = {"messages": [{"role": "user", "content": prompt}]}
    config = {"configurable": {"thread_id": thread_id}} if thread_id else {}
    # Prevent infinite tool call loops — sized by the caller when the task
    # needs more than a handful of calls. A fixed 10 cut the integration
    # reviewer off live (2026-10-04) after 4 reads + 1 write of 5 files.
    config["recursion_limit"] = recursion_limit or 10

    final_response = None
    if call_timeout is None:
        # No cap unless the caller asks — same "prove it's needed per call
        # site" rule as Path A. Genuinely unprotected against a stalled
        # stream (see _stream_agent_with_timeout's docstring) if left
        # unset; changing the default for every existing caller is out of
        # scope here.
        async for chunk in agent.astream(inputs, config=config, stream_mode="updates"):
            for _node, node_data in chunk.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        msg_type = type(msg).__name__
                        content = getattr(msg, "content", "")
                        tool_calls = getattr(msg, "tool_calls", [])
                        abi_logging(
                            f"[🔄] Agent msg: type={msg_type}, "
                            f"content={str(content)[:100] if content else '(empty)'}, "
                            f"tool_calls={len(tool_calls)}"
                        )
                        if content and msg_type != "ToolMessage":
                            final_response = _extract_text(content)
    else:
        try:
            final_response = await _stream_agent_with_timeout(agent, inputs, config, call_timeout)
        except asyncio.TimeoutError:
            abi_logging(
                f"[⚠️] Agent stream stalled (no chunk for {call_timeout}s) — "
                "retrying once with a fresh agent",
                level="warning",
            )
            retry_llm = create_llm(llm_config)
            retry_agent = create_agent(
                model=retry_llm, tools=actual_tools,
                system_prompt=enforced_system_prompt, checkpointer=checkpointer,
            )
            try:
                final_response = await _stream_agent_with_timeout(retry_agent, inputs, config, call_timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Agent stream stalled twice ({call_timeout}s each) — "
                    "the model server appears stuck, not just slow."
                )

    # ── Enforcement: check if required tools were used ──────────
    if tracker:
        missing = tracker.get_missing()
        if missing:
            abi_logging(f"[⚠️] Required tools not used by LLM: {missing}. Retrying with enforcement...")

            # Retry: explicit instruction to use the tools
            from abi_core.common.prompts.framework import ENFORCEMENT_RETRY_SYSTEM_PROMPT
            retry_prompt = tracker.get_enforcement_prompt(final_response or "")
            retry_agent = create_agent(
                model=llm,
                tools=actual_tools,
                system_prompt=ENFORCEMENT_RETRY_SYSTEM_PROMPT,
                checkpointer=None,
            )
            retry_inputs = {"messages": [{"role": "user", "content": retry_prompt}]}
            retry_config = {"recursion_limit": 10}  # Prevent infinite loops
            if call_timeout is None:
                async for chunk in retry_agent.astream(retry_inputs, config=retry_config, stream_mode="updates"):
                    for _node, node_data in chunk.items():
                        if "messages" in node_data:
                            for msg in node_data["messages"]:
                                msg_type = type(msg).__name__
                                content = getattr(msg, "content", "")
                                if content and msg_type != "ToolMessage":
                                    final_response = _extract_text(content)
            else:
                try:
                    final_response = await _stream_agent_with_timeout(
                        retry_agent, retry_inputs, retry_config, call_timeout
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(
                        f"Agent enforcement-retry stream stalled ({call_timeout}s) — "
                        "the model server appears stuck, not just slow."
                    )

            # Check again after retry
            still_missing = tracker.get_missing()
            if still_missing:
                abi_logging(f"[🔧] Fallback: executing {still_missing} programmatically")
                tracker.execute_fallback(final_response or "")

    return final_response or ""


async def invoke_structured(
    llm_config: Dict[str, Any],
    prompt: str,
    schema: Any,
    thread_id: str = None,
    system_prompt: str = None,
    call_timeout: float = None,
):
    """Like ``invoke()``'s Path A, but forces the response to match a
    Pydantic schema via ``with_structured_output`` instead of hoping a
    plain-text prompt instruction ("respond only in JSON") gets followed.

    Added after a live, reproduced failure: switching the Planner from
    qwen3 to devstral:24b (both "tools"-capable per `ollama show`) broke
    plan generation — devstral answered `PLANNER_COT_INSTRUCTIONS`'
    "respond only in JSON" instruction with a plain conversational
    paragraph instead, no JSON at all, silently degrading to
    `clean_llm_json()`'s single-task fallback (objective="Complete user
    request", the raw prose as the one task's description). This isn't a
    parsing bug — `clean_llm_json()` correctly found no JSON to parse — the
    model just didn't follow that instruction. Different providers/models
    already showed different failure modes on this same prompt-only
    contract (qwen3: usable but occasionally under-detailed; Gemini:
    reliable; devstral: ignored it outright) — that pattern itself is
    reason enough not to keep depending on any given model choosing to
    comply on its own.

    `with_structured_output(schema, method="json_schema")` uses Ollama's
    (and the other providers') grammar-constrained decoding — the schema is
    enforced at the token-sampling level server-side, not requested via
    prompt text, so it holds regardless of whether a given model's own
    training biases it toward conversational replies. Already proven
    for the Orchestrator's routing decision
    (`abi_core.agent.routing_tools.build_routing_decision_schema`) — this
    reuses the same mechanism for the Planner's decomposition call.

    Returns an instance of `schema` (a Pydantic model), not a string —
    callers get validated data directly, no `clean_llm_json()` step needed.
    """
    llm = create_llm(llm_config)
    structured_llm = llm.with_structured_output(schema, method="json_schema")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Same call_timeout contract as invoke()'s Path A — opt-in per call
    # site, asyncio.to_thread so a stuck call can actually be abandoned.
    # See invoke()'s own comment for why a bare asyncio.wait_for doesn't
    # work here.
    if call_timeout is None:
        return await structured_llm.ainvoke(messages)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(structured_llm.invoke, messages), timeout=call_timeout
        )
    except asyncio.TimeoutError:
        abi_logging(
            f"[⚠️] Structured LLM call timed out after {call_timeout}s — retrying once "
            "with a fresh client",
            level="warning",
        )
        retry_llm = create_llm(llm_config)
        retry_structured_llm = retry_llm.with_structured_output(schema, method="json_schema")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(retry_structured_llm.invoke, messages), timeout=call_timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Structured LLM call timed out twice ({call_timeout}s each) — "
                "the model server appears stuck, not just slow."
            )
