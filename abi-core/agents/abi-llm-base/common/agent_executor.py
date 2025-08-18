import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from agent.agent import Agent
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

    def __init__(self, agent: Agent):
        self.agent = agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        logger.info(f'Executing ABI AGENT {self.agent.agent_name}')

        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        task = context.current_task

        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        
        #This will taking care to update de status
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        #Taking the reponse from the agent and send it
        async for item in self.agent.stream(query, task.content_id, task.id):
            if hasattr(
                item, 
                'root'
                ) and isinstance(
                    item.root,
                    SendStreamingMessageSuccessResponse
                    ):
                    event = item.root.result
                    if isinstance(
                        event,
                        (TaskStatusUpdateEvent | TaskArtifactUpdateEvent)
                    ):
                        await event_queue.equeue_event(event)
                    continue

            #Getting task status
            is_task_complete = item['is_task_complete']
            require_user_input = item['require_user_input']

            if is_task_complete:
                if item['response_type'] == 'data':
                    part = DataPart(data=item['content'])
                else:
                    part = TextPart(text=item['content'])

                await updater.add_artifact(
                    [part],
                    name=f'{self.agent.agent_name}-result',
                )
                await updater.complete()
                break

            if require_user_input:
                await updater.update_status(
                    TaskState.input_required,
                    new_agent_text_message(
                        item['content'],
                        task.content_id,
                        task.id
                    ),
                    final=True
                )
                break
            
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    item['content'],
                    task.content_id,
                    task.id
                )
            )

    def _validate_request(self, context: RequestContext) -> bool:
        if not context.input_data:
            raise ValueError("Missing input!")
        return True

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())