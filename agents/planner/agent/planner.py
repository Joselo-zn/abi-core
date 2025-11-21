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
from common.utils import abi_logging
from .models.agent_models import PlannerResponse
from agent.agent import AbiAgent

from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

MODEL_NAME = os.getenv('MODEL_NAME', 'llama3.2:3b')

class AbiPlannerAgent(AbiAgent):
    """Planner devide a Big Plan y small executable actions/task"""
    def __init__(self):
        super().__init__(
            agent_name='Planner Agent',
            description='Devide a Big Plan y small executable actions/task',
            content_types=['text', 'text/plain']
        )
        memory = InMemorySaver()
        self.llm = ChatOllama(model=MODEL_NAME, temperature=0.0)
        abi_logging(f'[🚀] Starting ABI {self.agent_name}')
        self.abi_planner = create_react_agent(
            self.llm,
            tools=[],
            checkpointer=memory,
            prompt=prompts.PLANNER_COT_INSTRUCTIONS,
            response_format = PlannerResponse
        )

    def invoke(self, query, sessionId) -> str:
        config = {'configurable': {'thread_id': sessionId}}
        self.abi_planner.invoke(
            {"message": [{"role": "user", "content": query}],
            "user_preferences": {
                "style": "technical", 
                "verbosity": "detailed"
                },
            }, config={"configurable": {"thread": sessionId}})
        return self.actor_response(config)
    
    async def stream(
            self, query, sessionId, task_id
    ) -> AsyncIterable[dict[str,any]]:
        abi_logging(f'[*] Running stream session {sessionId} {task_id} with input {query}')
        config = {'configurable': {'thread_id': sessionId}}
        for items in self.abi_planner.stream(
            {"messages": [("user", query)]},
            config,
            stream_mode="values",
        ):
            
            message = items['messages'][-1]

            if isinstance(message, AIMessage):
                yield {
                    'response_type': 'text',
                    'is_task_completed': False,
                    'require_user_input': False,
                    'content': message.content
                }
        yield self.get_agent_response(config)
    
    def get_agent_response(self, config) -> dict[str,any]:
        current_state = self.abi_planner.get_state(config)
        structured_response = current_state.values.get('structured_response')
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
                    'is_task_completed': False,
                    'require_user_input': True,
                    'content': structured_response.question,
                }
            if structured_response.status == 'completed':
                return {
                    'response_type': 'data',
                    'is_task_completed': True,
                    'require_user_input': False,
                    'content': structured_response.content.model_dump(),
                }
        return {
            'is_task_completed': False,
            'require_user_input': True,
            'content': 'We are unable to process your request at the moment. Please try again.',
        }    
