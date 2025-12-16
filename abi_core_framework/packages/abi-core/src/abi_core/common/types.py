"""
Common type definitions for ABI-Core.

This module provides shared type definitions and Pydantic models used
throughout the ABI-Core framework.
"""

from typing import Any, Dict, Union
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """
    Server configuration model.
    
    Configuration for MCP servers and other service endpoints.
    
    Attributes:
        host: Server hostname or IP address
        port: Server port number
        transport: Transport protocol (e.g., 'sse', 'http', 'websocket')
        url: Complete server URL
        
    Example:
        >>> config = ServerConfig(
        ...     host="localhost",
        ...     port=8080,
        ...     transport="sse",
        ...     url="http://localhost:8080"
        ... )
    """

    host: str = Field(
        description="Server hostname or IP address"
    )
    port: int = Field(
        description="Server port number",
        gt=0,
        lt=65536
    )
    transport: str = Field(
        description="Transport protocol (sse, http, websocket)"
    )
    url: str = Field(
        description="Complete server URL"
    )


class AgentResponse(BaseModel):
    """
    Standard response schema for agent operations.
    
    This model defines the structure of responses returned by agents
    during task execution. It supports both streaming and non-streaming
    responses.
    
    Attributes:
        content: The response content (string or structured dict)
        is_task_complete: Whether the agent has completed the task
        require_user_input: Whether the agent needs additional user input
        
    Example:
        >>> response = AgentResponse(
        ...     content="Task completed successfully",
        ...     is_task_complete=True,
        ...     require_user_input=False
        ... )
        >>> 
        >>> # Structured response
        >>> response = AgentResponse(
        ...     content={"result": "data", "status": "success"},
        ...     is_task_complete=True,
        ...     require_user_input=False
        ... )
    """

    content: Union[str, Dict[str, Any]] = Field(
        description='The content of the response. Can be a string or structured data.'
    )
    
    is_task_complete: bool = Field(
        description='Whether the task is complete. True if finished, False if ongoing.'
    )
    
    require_user_input: bool = Field(
        description='Whether the agent requires additional user input to continue.'
    )
