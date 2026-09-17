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

from typing import Any, Dict

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


async def invoke(
    llm_config: Dict[str, Any],
    prompt: str,
    tools: list = None,
    thread_id: str = None,
    system_prompt: str = None,
    required_tools: list = None,
) -> str:
    """Unified LLM invocation with optional tool enforcement.

    Args:
        llm_config: Provider config dict for create_llm().
        prompt: The user/system message to send.
        tools: Optional list of LangChain tools.
        thread_id: Optional session ID for conversation memory.
        system_prompt: Optional system instructions.
        required_tools: List of tool names that MUST be called.
            If declared, the framework enforces usage with retry + fallback.

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

        response = await llm.ainvoke(messages)
        return response.content if hasattr(response, "content") else str(response)

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

    checkpointer = None
    if thread_id:
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
    config["recursion_limit"] = 10  # Prevent infinite tool call loops

    final_response = None
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
                        final_response = content

    # ── Enforcement: check if required tools were used ──────────
    if tracker:
        missing = tracker.get_missing()
        if missing:
            abi_logging(f"[⚠️] Required tools not used by LLM: {missing}. Retrying with enforcement...")

            # Retry: explicit instruction to use the tools
            retry_prompt = tracker.get_enforcement_prompt(final_response or "")
            retry_agent = create_agent(
                model=llm,
                tools=actual_tools,
                system_prompt="You MUST call the required tools. Do not explain. Just call them.",
                checkpointer=None,
            )
            retry_inputs = {"messages": [{"role": "user", "content": retry_prompt}]}
            retry_config = {"recursion_limit": 10}  # Prevent infinite loops
            async for chunk in retry_agent.astream(retry_inputs, config=retry_config, stream_mode="updates"):
                for _node, node_data in chunk.items():
                    if "messages" in node_data:
                        for msg in node_data["messages"]:
                            msg_type = type(msg).__name__
                            content = getattr(msg, "content", "")
                            if content and msg_type != "ToolMessage":
                                final_response = content

            # Check again after retry
            still_missing = tracker.get_missing()
            if still_missing:
                abi_logging(f"[🔧] Fallback: executing {still_missing} programmatically")
                tracker.execute_fallback(final_response or "")

    return final_response or ""
