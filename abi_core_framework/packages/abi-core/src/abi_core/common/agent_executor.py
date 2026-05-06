import json

from abi_core.common.utils import abi_logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from abi_core.agent.agent import AbiAgent
from a2a.types import (
    DataPart,
    InvalidParamsError,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
    UnsupportedOperationError
)


class ABIAgentExecutor(AgentExecutor):
    """Execute ABI agents"""

    def __init__(self, agent: AbiAgent):
        self.agent = agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        abi_logging(f'Executing ABI AGENT {self.agent.agent_name}')

        self._validate_request(context)

        query = context.get_user_input()
        task = context.current_task

        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        
        #This will taking care to update de status
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            #Taking the reponse from the agent and send it
            async for item in self.agent.stream(query, task.context_id, task.id):
                if hasattr(item, 'root'):
                    abi_logging(f'ITEM ROOT TYPE: {type(item.root)}')
                if hasattr(
                    item, 
                    'root'
                    ) and isinstance(
                        item.root,
                        SendMessageSuccessResponse
                        ):
                        event = item.root.result
                        if isinstance(
                            event,
                            (TaskStatusUpdateEvent | TaskArtifactUpdateEvent)
                        ):
                            await event_queue.equeue_event(event)
                        continue

                #Getting task status
                is_task_completed = item.get('is_task_completed', False)
                require_user_input = item.get('require_user_input', True)
                if is_task_completed:
                    content = item['content']
                    if isinstance(content, dict):
                        part = DataPart(data=content)
                    elif isinstance(content, str):
                        part = TextPart(text=content)
                    else:
                        part = TextPart(text=str(content))
                    await updater.add_artifact(
                        [part],
                        name=f'{self.agent.agent_name}-result',
                    )
                    await updater.complete()
                    break

                if require_user_input:
                    content = item['content']
                    text_content = content if isinstance(content, str) else json.dumps(content)
                    abi_logging(f'REQUIERE INPUT {text_content[:200]}')
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            text_content,
                            task.context_id,
                            task.id
                        ),
                        final=True
                    )
                    break
                status_content = item['content']
                status_text = status_content if isinstance(status_content, str) else json.dumps(status_content)
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        status_text,
                        task.context_id,
                        task.id
                    )
                )
        finally:
            # Flush logs to MinIO after every request (all agents)
            try:
                from abi_core.common.utils import flush_logs
                _tid = task.id if task else None
                await flush_logs(agent_name=self.agent.agent_name, task_id=_tid)
            except Exception:
                pass  # never break the request pipeline

            # Post-response cleanup hook (used by ephemeral agents)
            if hasattr(self.agent, 'on_response_sent') and self.agent.on_response_sent:
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
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
