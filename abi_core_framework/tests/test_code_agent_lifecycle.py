"""
Tests for the code agent lifecycle pieces that run without a live agent:
the kept generation conversation, the idle watchdog, execute_step honouring
a step's timeout, and invoke's external checkpointer.
Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.2-code-agent-lifecycle.md
"""

import asyncio

import pytest

from abi_agents.zombie.agent import lifecycle


def test_generation_transcript_reads_the_kept_conversation():
    from langchain_core.messages import AIMessage
    from langgraph.graph import START, MessagesState, StateGraph

    graph = StateGraph(MessagesState)
    graph.add_node("model", lambda s: {"messages": [AIMessage(
        content="I will import Player from player.py",
        tool_calls=[{"name": "write_file", "args": {"filename": "game.py"}, "id": "1"}],
    )]})
    graph.add_edge(START, "model")
    graph.compile(checkpointer=lifecycle.generation_memory()).invoke(
        {"messages": [("user", "write game.py")]},
        {"configurable": {"thread_id": lifecycle.GENERATION_THREAD}},
    )
    transcript = lifecycle.generation_transcript()
    assert "[human] write game.py" in transcript
    assert "import Player" in transcript and "[tool call] write_file" in transcript


def test_watchdog_resets_on_contact_and_ends_when_silent(monkeypatch):
    ended = []

    async def fake_terminate(name, reason):
        ended.append(reason)

    monkeypatch.setattr(lifecycle, "terminate_now", fake_terminate)
    monkeypatch.setattr(lifecycle, "terminate_requested", False)
    monkeypatch.setattr(lifecycle, "_watchdog", None)

    async def scenario():
        lifecycle.start_watchdog("agent", 0.3)
        await asyncio.sleep(0.2)
        lifecycle.touch()
        await asyncio.sleep(0.2)
        assert ended == []          # 0.4 s elapsed, only 0.2 s silent
        await asyncio.sleep(0.6)

    asyncio.run(scenario())
    assert len(ended) == 1 and "no contact from the reviewer" in ended[0]


def test_execute_step_honours_step_timeout():
    from abi_core.agent.abi_core_app import AbiCore

    core = AbiCore(config=object(), agent_card=None)

    @core.step(name="slow", timeout=0.05)
    async def slow():
        await asyncio.sleep(1)

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(core.execute_step("slow"))


def test_invoke_checkpointer_needs_thread_id():
    from abi_core.agent.llm_provider import invoke

    with pytest.raises(ValueError):
        asyncio.run(invoke({"provider": "ollama", "model": "x"}, "p", tools=[object()],
                           checkpointer=lifecycle.generation_memory()))
