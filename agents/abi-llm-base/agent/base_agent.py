# agent/base_agent.py
import logging
from abc import ABC
from pydantic import BaseModel, Field


class ModelAgent(BaseModel, ABC):
    """Base class for agents."""

    model_config = {
        'arbitrary_types_allowed': True,
        'extra': 'allow',
    }

    agent_name: str = Field(
        description='The name of the agent.',
    )

    description: str = Field(
        description="A brief description of the agent's purpose.",
    )

    content_types: list[str] = Field(description='Supported content types.')



class BaseAgent:
    def __init__(self, agent_name: str, description: str, content_types: list[str]):
        self.agent_name = agent_name
        self.description = description
        self.content_types = content_types
        self.logger = logging.getLogger(agent_name)
        self.state = {}

    def register(self):
        self.logger.info(f"[{self.agent_name}] Registered.")

    def receive(self, task):
        self.logger.info(f"[{self.agent_name}] Received task: {task}")

    def clear_state(self):
        self.state.clear()
        self.logger.info(f"[{self.agent_name}] State cleared.")

