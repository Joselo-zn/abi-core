"""
LLM Provider — Unified factory for creating LangChain chat models.

Supports three scenarios:
1. Cloud managed: Bedrock, Azure OpenAI, Vertex AI
2. Self-hosted: Ollama (local or remote)
3. Direct APIs: OpenAI, Anthropic, Google Gemini, Grok (xAI)

All providers are imported lazily to avoid forcing unnecessary dependencies.

Usage:
    from abi_core.agent.llm_provider import create_llm

    llm = create_llm({
        "provider": "ollama",
        "model": "qwen2.5:3b",
        "temperature": 0.1,
        "base_url": "http://localhost:11434",
    })

    llm = create_llm({
        "provider": "bedrock",
        "model": "anthropic.claude-3-sonnet-20240229-v1:0",
        "aws_region": "us-east-1",
        "temperature": 0.1,
    })
"""

from typing import Any, Dict

from abi_core.common.utils import abi_logging


def create_llm(llm_config: Dict[str, Any]):
    """
    Create a LangChain BaseChatModel from a config dictionary.

    Required keys:
        provider: str — one of: ollama, openai, anthropic, gemini, grok,
                        bedrock, azure, vertex
        model: str — model name/id

    Common optional keys:
        temperature: float (default 0.1)
        api_key: str (for API-based providers)
        base_url: str (for ollama or custom endpoints)

    Cloud-specific keys:
        aws_region: str (bedrock)
        azure_deployment: str (azure)
        azure_endpoint: str (azure)
        vertex_project: str (vertex)
        vertex_location: str (vertex)

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        ValueError: If provider is unknown or required deps are missing.
    """
    provider = llm_config.get("provider", "ollama").lower().strip()
    model = llm_config.get("model", "qwen2.5:3b")
    temperature = float(llm_config.get("temperature", 0.1))
    api_key = llm_config.get("api_key", "")
    base_url = llm_config.get("base_url", "")

    abi_logging(f"[🤖] Creating LLM: provider={provider}, model={model}")

    # ── Ollama (self-hosted) ────────────────────────────────────
    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ValueError("langchain-ollama is required for provider 'ollama'. pip install langchain-ollama")
        url = base_url or "http://localhost:11434"
        llm = ChatOllama(model=model, base_url=url, temperature=temperature)
        abi_logging(f"[✅] Ollama LLM ready: {model} at {url}")
        return llm

    # ── OpenAI (direct API) ─────────────────────────────────────
    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ValueError("langchain-openai is required for provider 'openai'. pip install langchain-openai")
        kwargs = {"model": model, "temperature": temperature}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        llm = ChatOpenAI(**kwargs)
        abi_logging(f"[✅] OpenAI LLM ready: {model}")
        return llm

    # ── Anthropic (direct API) ──────────────────────────────────
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ValueError("langchain-anthropic is required for provider 'anthropic'. pip install langchain-anthropic")
        kwargs = {"model": model, "temperature": temperature}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        llm = ChatAnthropic(**kwargs)
        abi_logging(f"[✅] Anthropic LLM ready: {model}")
        return llm

    # ── Google Gemini (direct API) ──────────────────────────────
    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ValueError("langchain-google-genai is required for provider 'gemini'. pip install langchain-google-genai")
        kwargs = {"model": model, "temperature": temperature}
        if api_key:
            kwargs["google_api_key"] = api_key
        llm = ChatGoogleGenerativeAI(**kwargs)
        abi_logging(f"[✅] Gemini LLM ready: {model}")
        return llm

    # ── Grok / xAI (OpenAI-compatible API) ──────────────────────
    if provider == "grok":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ValueError("langchain-openai is required for provider 'grok'. pip install langchain-openai")
        url = base_url or "https://api.x.ai/v1"
        kwargs = {"model": model, "temperature": temperature, "base_url": url}
        if api_key:
            kwargs["api_key"] = api_key
        llm = ChatOpenAI(**kwargs)
        abi_logging(f"[✅] Grok/xAI LLM ready: {model} at {url}")
        return llm

    # ── AWS Bedrock (cloud managed) ─────────────────────────────
    if provider == "bedrock":
        try:
            from langchain_aws import ChatBedrock
        except ImportError:
            raise ValueError("langchain-aws is required for provider 'bedrock'. pip install langchain-aws")
        region = llm_config.get("aws_region", "us-east-1")
        llm = ChatBedrock(
            model_id=model,
            region_name=region,
            model_kwargs={"temperature": temperature},
        )
        abi_logging(f"[✅] Bedrock LLM ready: {model} in {region}")
        return llm

    # ── Azure OpenAI (cloud managed) ────────────────────────────
    if provider == "azure":
        try:
            from langchain_openai import AzureChatOpenAI
        except ImportError:
            raise ValueError("langchain-openai is required for provider 'azure'. pip install langchain-openai")
        deployment = llm_config.get("azure_deployment", model)
        endpoint = llm_config.get("azure_endpoint", "")
        kwargs = {
            "azure_deployment": deployment,
            "temperature": temperature,
        }
        if endpoint:
            kwargs["azure_endpoint"] = endpoint
        if api_key:
            kwargs["api_key"] = api_key
        llm = AzureChatOpenAI(**kwargs)
        abi_logging(f"[✅] Azure OpenAI LLM ready: {deployment}")
        return llm

    # ── Google Vertex AI (cloud managed) ────────────────────────
    if provider == "vertex":
        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError:
            raise ValueError("langchain-google-vertexai is required for provider 'vertex'. pip install langchain-google-vertexai")
        project = llm_config.get("vertex_project", "")
        location = llm_config.get("vertex_location", "us-central1")
        kwargs = {"model_name": model, "temperature": temperature, "location": location}
        if project:
            kwargs["project"] = project
        llm = ChatVertexAI(**kwargs)
        abi_logging(f"[✅] Vertex AI LLM ready: {model} in {location}")
        return llm

    raise ValueError(
        f"Unknown LLM provider: '{provider}'. "
        f"Supported: ollama, openai, anthropic, gemini, grok, bedrock, azure, vertex"
    )


async def invoke(
    llm_config: Dict[str, Any],
    prompt: str,
    tools: list = None,
    thread_id: str = None,
    system_prompt: str = None,
) -> str:
    """Unified LLM invocation for any node in the system.

    Covers 4 use cases:
    - LLM only, no context:    invoke(config, "classify this")
    - LLM only, with context:  invoke(config, "summarize", thread_id="abc")
    - Agent + tools, no ctx:   invoke(config, "verify tool", tools=[search])
    - Agent + tools, with ctx:  invoke(config, query, tools=[find], thread_id="s1")

    Args:
        llm_config: Provider config dict for create_llm().
        prompt: The user/system message to send.
        tools: Optional list of LangChain tools. If provided, creates
               a full agent that can call tools. If None, uses LLM directly.
        thread_id: Optional session ID for conversation memory.
               If provided, uses MemorySaver checkpointer so the LLM
               retains history across calls with the same thread_id.
        system_prompt: Optional system instructions prepended to the call.

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

    checkpointer = None
    if thread_id:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt or "",
        checkpointer=checkpointer,
    )
    abi_logging(f'CREATE AGENT CALLED WITH TOOLS {tools}')
    inputs = {"messages": [{"role": "user", "content": prompt}]}
    config = {"configurable": {"thread_id": thread_id}} if thread_id else {}

    final_response = None
    async for chunk in agent.astream(inputs, config=config, stream_mode="updates"):
        for _node, node_data in chunk.items():
            if "messages" in node_data:
                for msg in node_data["messages"]:
                    if hasattr(msg, "content") and msg.content:
                        final_response = msg.content

    return final_response or ""
