"""
Base ABI Agent Class
Core agent functionality for ABI Framework
"""

import asyncio
from typing import Any, Dict, List, AsyncIterable, Optional

from abi_core.common.utils import abi_logging
from abi_core.agent.llm_provider import create_llm
from abi_core.agent.agent_response import AgentResponse

# Heartbeat interval in seconds — must be under proxy timeout (CloudFront = 30s)
_HEARTBEAT_INTERVAL = 15


class AbiAgent:
    """Base class for all ABI agents.

    Handles LLM creation, LangChain agent wiring, and a default
    ``stream()`` implementation so subclasses only need to pass
    configuration.  Override ``stream()`` for custom behaviour.

    The optional ``tool_graph`` attribute is injected by ``AbiCore``
    when tasks/tools are registered via ``@app.task()`` / ``@app.tool()``
    decorators.  Subclasses can use ``self.tool_graph`` to execute
    deterministic DAG pipelines.

    Args:
        agent_name: Identifier for this agent.
        description: Human-readable description.
        llm_config: Dict consumed by ``create_llm()`` (provider, model, etc.).
        tools: List of LangChain-compatible tools for the agent.
        system_prompt: System prompt / instructions for the agent.
        content_types: Accepted content types (default: text/plain).
    """

    def __init__(
        self,
        agent_name: str,
        description: str,
        llm_config: Dict[str, Any],
        tools: List = None,
        system_prompt: str = "",
        content_types: List[str] = None,
    ):
        self.agent_name = agent_name
        self.description = description
        self.llm_config = llm_config
        self.content_types = content_types or ["text", "text/plain"]

        # Injected by AbiCore when @app.task()/@app.tool() are used
        self.tool_graph = None  # Optional[ToolExecutionGraph]
        self.extra_tools: List = []  # LangChain tools from @app.tool()

        # Create LLM via unified provider
        self.llm = create_llm(llm_config)

        # Merge explicit tools with any injected by AbiCore later
        self._base_tools = tools or []

        # Create LangChain agent with tools
        from langchain.agents import create_agent

        self.agent = create_agent(
            model=self.llm,
            tools=self._base_tools,
            system_prompt=system_prompt,
        )

        abi_logging(f"[🚀] {agent_name} agent ready")

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[Dict[str, Any]]:
        """Process query and stream responses with keepalive heartbeats.

        Runs the LLM call in a background task and yields periodic
        ``AgentResponse.status()`` heartbeats every ~15 s so that
        proxies like CloudFront (30 s idle timeout) don't close the
        SSE connection.

        Override in subclasses for custom behaviour (e.g. Planner,
        Orchestrator).

        Args:
            query: User query to process.
            context_id: Context identifier.
            task_id: Task identifier.

        Yields:
            AgentResponse instances (status heartbeats + final result).
        """
        abi_logging(f'[📝] {self.agent_name} processing: {query[:100]}...')

        # Immediate status so the client knows we started
        yield AgentResponse.status(
            "Processing...",
            agent=self.agent_name,
            context_id=context_id,
            task_id=task_id,
        )

        result_holder: Dict[str, Any] = {}

        async def _run_llm():
            """Execute LLM in background and store result."""
            inputs = {"messages": [{"role": "user", "content": query}]}
            final_response = None
            async for chunk in self.agent.astream(inputs, stream_mode="updates"):
                for _node_name, node_data in chunk.items():
                    if "messages" in node_data:
                        for msg in node_data["messages"]:
                            if hasattr(msg, 'content') and msg.content:
                                final_response = msg.content
            result_holder['response'] = final_response

        llm_task = asyncio.create_task(_run_llm())

        try:
            # Heartbeat loop — yield status every _HEARTBEAT_INTERVAL seconds
            while not llm_task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(llm_task), timeout=_HEARTBEAT_INTERVAL
                    )
                except asyncio.TimeoutError:
                    # LLM still working — send heartbeat
                    if not llm_task.done():
                        yield AgentResponse.status(
                            "Still working...",
                            agent=self.agent_name,
                            context_id=context_id,
                            task_id=task_id,
                        )

            # Propagate any exception from the LLM task
            await llm_task

            final_response = result_holder.get('response')
            if final_response:
                yield AgentResponse.success(
                    final_response,
                    agent=self.agent_name,
                    model=self.llm_config.get('model', 'unknown'),
                    context_id=context_id,
                    task_id=task_id,
                )
            else:
                yield AgentResponse.empty()

        except Exception as e:
            abi_logging(f'[❌] Error in {self.agent_name}: {e}', level='error')
            if not llm_task.done():
                llm_task.cancel()
            yield AgentResponse.error(str(e), agent=self.agent_name)

    def get_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "name": self.agent_name,
            "description": self.description,
            "content_types": self.content_types,
        }
