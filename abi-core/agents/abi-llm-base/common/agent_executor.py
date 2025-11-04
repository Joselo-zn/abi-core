import logging

from common.utils import abi_logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from agent.agent import AbiAgent
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

logger = logging.getLogger(__name__)


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
                    abi_logging(f"ITEM ROOT EVENT: {type(event)}")
                    if isinstance(
                        event,
                        (TaskStatusUpdateEvent | TaskArtifactUpdateEvent)
                    ):
                        await event_queue.equeue_event(event)
                    continue

            #Getting task status
            is_task_completed = item['is_task_completed']
            require_user_input = item['require_user_input']
            abi_logging(f'ITEM RESPONSE {is_task_completed} {dir(item.keys())}')
            abi_logging(f'ITEM RESPONSE {dir(item.values())}')
            if is_task_completed:
                if item['response_type'] == 'data':
                    part = DataPart(data=item['content'])
                else:
                    part = TextPart(text=item['content'])
                abi_logging(f"ADDING ARTIFACT: {part}")
                await updater.add_artifact(
                    [part],
                    name=f'{self.agent.agent_name}-result',
                )
                abi_logging(f"UPDATER ARTIFACT: {updater, type(updater)}")
                await updater.complete()
                break

            if require_user_input:
                content = item['content']
                abi_logging(f'REQUIERE INPUT {content}')
                await updater.update_status(
                    TaskState.input_required,
                    new_agent_text_message(
                        item['content'],
                        task.context_id,
                        task.id
                    ),
                    final=True
                )
                break
            abi_logging(f'UPDATING AND SENDING !!!')
            abi_logging(f'UPDATER {dir(updater)}')
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    item['content'],
                    task.context_id,
                    task.id
                )
            )

    def _validate_request(self, context: RequestContext) -> bool:
        if not context.get_user_input():
            raise ValueError("Missing input!")

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
