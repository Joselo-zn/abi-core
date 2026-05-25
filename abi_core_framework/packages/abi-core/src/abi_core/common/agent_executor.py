import json

from abi_core.common.utils import abi_logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.utils.errors import A2AError
from abi_core.agent.agent import AbiAgent
from a2a.types import (
    Part,
    Task,
    TaskState,
    UnsupportedOperationError,
)


class ABIAgentExecutor(AgentExecutor):
    """Execute ABI agents via the a2a-sdk 1.0 AgentExecutor interface."""

    def __init__(self, agent: AbiAgent):
        self.agent = agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        abi_logging(f"Executing ABI AGENT {self.agent.agent_name}")

        self._validate_request(context)

        query = context.get_user_input()
        task = context.current_task
        task_id = context.task_id or ""
        context_id = context.context_id or ""

        updater = TaskUpdater(event_queue, task_id, context_id)

        # Enqueue Task object first (required by a2a-sdk 1.0)
        from a2a.types import Task as A2ATask, TaskStatus
        from google.protobuf.timestamp_pb2 import Timestamp
        from datetime import datetime, timezone
        ts = Timestamp()
        ts.FromDatetime(datetime.now(timezone.utc))
        initial_task = A2ATask(
            id=task_id,
            context_id=context_id,
            status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED, timestamp=ts),
        )
        await event_queue.enqueue_event(initial_task)

        try:
            async for item in self.agent.stream(query, context_id, task_id):
                is_task_completed = item.get("is_task_completed", False)
                require_user_input = item.get("require_user_input", True)

                if is_task_completed:
                    content = item["content"]
                    if isinstance(content, dict):
                        part = Part(text=json.dumps(content))
                    elif isinstance(content, str):
                        part = Part(text=content)
                    else:
                        part = Part(text=str(content))

                    await updater.add_artifact(
                        [part],
                        name=f"{self.agent.agent_name}-result",
                    )
                    await updater.complete()
                    break

                if require_user_input:
                    content = item["content"]
                    text_content = content if isinstance(content, str) else json.dumps(content)
                    abi_logging(f"REQUIERE INPUT {text_content[:200]}")
                    msg = updater.new_agent_message([Part(text=text_content)])
                    await updater.requires_input(msg)
                    break

                # Status update (working)
                status_content = item["content"]
                status_text = status_content if isinstance(status_content, str) else json.dumps(status_content)
                msg = updater.new_agent_message([Part(text=status_text)])
                await updater.update_status(TaskState.TASK_STATE_WORKING, msg)

        finally:
            # Flush logs to MinIO after every request
            try:
                from abi_core.common.utils import flush_logs
                await flush_logs(agent_name=self.agent.agent_name, task_id=task_id)
            except Exception:
                pass

            # Post-response cleanup hook (used by ephemeral agents)
            if hasattr(self.agent, "on_response_sent") and self.agent.on_response_sent:
                import asyncio
                asyncio.ensure_future(self._deferred_cleanup())

    def _validate_request(self, context: RequestContext) -> bool:
        if not context.get_user_input():
            raise ValueError("Missing input!")

    async def _deferred_cleanup(self):
        """Run agent cleanup after a short delay so the HTTP response is sent first."""
        import asyncio
        await asyncio.sleep(1)
        try:
            await self.agent.on_response_sent()
        except Exception as e:
            print(f"[⚠️] Deferred cleanup error: {e}", flush=True)

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise A2AError(error=UnsupportedOperationError())
