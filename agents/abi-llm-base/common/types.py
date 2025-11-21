# type: ignore

from typing import Any, Literal

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server Confgiguration."""

    host: str
    port: int
    transport: str
    url: str

class AgentResponse(BaseModel):
    """Output schema for the Agent."""

    content: str | dict = Field(description='The content of the response.')
    is_task_complete: bool = Field(description='Whether the task is complete.')
    require_user_input: bool = Field(
        description='Whether the agent requires user input.'
    )
