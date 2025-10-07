import logging
import os

from collections.abc import AsyncIterable

from a2a.types import (
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent
)
from common import prompts
from agent.agent import AbiAgent
from agent.models.agent_models import PlannerResponse

from langchain_core.messages import AIMessage
from langchain_community.chat_models import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv('MODEL_NAME', 'tinyllama:latest')
memory = MemorySaver()

class AbiPlannerAgent(AbiAgent):
    """Planner devide a Big Plan y small executable actions/task"""
    def __init__(self, instructions):
        super().__init__(
            aget_name='Planner Agent',
            description='Devide a Big Plan y small executable actions/task',
            content_type=['text', 'text/plain']
        )

        self.instructions = instructions
        self.llm = ChatOllama(model_name=MODEL_NAME, temperature=0.0)
        logger.info(f'[🚀] Starting ABI Planner Agent')
        self.abi_planner = create_react_agent(
            self.llm,
            checkpointer=memory,
            prompt=prompts.PLANNER_COT_INSTRUCTIONS,
            reponse_format = PlannerResponse
        )

    def invoke(self, query, sessionId) -> str:
        config = {'configurable': {'thread_id': sessionId}}
        self.abi_planner.invoke(
            {'message': [('user', query)]}, 
            config
            )
        return self.actor_response(config)
    
    async def stream(
            self, query, sessinId, task_id
    ) -> AsyncIterable[dict[str,any]]:
        config = {'configurable': {'thread': sessinId}}
        input = {'message': [('user', query)]}

        logger.info(f'[*] Running stream session {sessinId} {task_id} with input {query}')

        for items in self.abi_planner.stream(input, config, stream_mode='values'):
            message = items['messages'][-1]
            if isinstance(message, AIMessage):
                yield {
                    'response_type': 'text',
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': message.content
                }
        yield self.get_agent_response(config)
    
    def get_agent_response(self, config) -> dict[str,any]:
        current_state = self.abi_planner.get_state(config)
        structured_response = current_state.value.get('structured_response')
        if structured_response and isinstance(
            structured_response, PlannerResponse
        ):
            if structured_response.status == 'input_required':
                return {
                    'reponse_type': 'text',
                    'is_task_completed': False,
                    'require_user_input': True,
                    'content': structured_response.question
                }
            if structured_response.status == 'error':
                return {
                    'response_type': 'text',
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.question,
                }
            if structured_response.status == 'completed':
                return {
                    'response_type': 'data',
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.content.model_dump(),
                }
        return {
            'is_task_complete': False,
            'require_user_input': True,
            'content': 'We are unable to process your request at the moment. Please try again.',
        }
