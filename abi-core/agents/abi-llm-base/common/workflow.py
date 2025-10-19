import json
import logging
import uuid

from collections.abc import AsyncIterable
from enum import Enum
from uuid import uuid4

import httpx
import networkx as nx

from a2a.client import A2AClient
from common.utils import get_mcp_server_config
from abi_mcp import client
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)

logger = logging.getLogger(__name__)

class Status(Enum):
    """Reprents the status of the workflow"""

    READY = 'READY'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    PAUSED = 'PAUSED'
    INITIALIZED = 'INITIALIZED'


class WorkflowNode:
    """Represents a single node in a Workflow Graph.

    Each node encapsulates a specific task to be executed, 
    such as finding an Agent Capabilities. It manage its own state
    and can execute its assigned task.
    """

    def __init__(
        self,
        task: str,
        node_key: str | None = None,
        node_label: str | None = None,

    ):
        self.id = str(uuid.uuid4())
        self.node_key = node_key
        self.node_label = node_label
        self.task = task
        self.result = None
        self.state = Status.READY

    async def get_planner_resource(self) -> AgentCard | None:
        logger.info(f'Getting resource for node {self.id}')
        config = get_mcp_server_config()
        async with client.init_session(
            config.host, config.port, config.transport
        ) as session:
            response = await client.find_resource(
                session, 'resource://agent_cards/planner_agent'
            )
            # ReadResourceResult has 'contents' attribute, not 'content'
            if hasattr(response, 'contents') and response.contents:
                data = json.loads(response.contents[0].text)
                if 'agent_card' in data and data['agent_card'] and len(data['agent_card']) > 0:
                    return AgentCard(**data['agent_card'][0])
                else:
                    logger.error(f"No agent_card found in response data: {data}")
                    return None
            else:
                logger.error("No content found in resource response")
                return None

    async def find_agent_for_task(self) -> AgentCard | None:
        logger.info(f'Find agent for task - {self.task}')
        config = get_mcp_server_config()
        async with client.init_session(
            config.host,
            config.port,
            config.transport
        ) as session:
            result = await client.find_agent(session, self.task)
            # CallToolsResult has 'content' attribute with different structure
            if hasattr(result, 'content') and result.content:
                try:
                    if isinstance(result.content, list) and result.content:
                        agent_card_json = json.loads(result.content[0].text)
                    else:
                        agent_card_json = result.content
                    
                    if agent_card_json:
                        return AgentCard(**agent_card_json)
                    else:
                        return None
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.error(f"Error parsing agent card data: {e}")
                    return None
            else:
                logger.error("No content found in tool result")
                return None

    async def run_node(
        self,
        query: str,
        task_id: str,
        context_id: str,
    ) -> AsyncIterable[dict[str, any]]:
        logger.info(f'Execute node {self.id}')
        logger.info(f'Node key: {self.node_key}')
        agent_card = None
        if self.node_key ==  'planner':
            logger.info('Getting planner resource...')
            agent_card = await self.get_planner_resource()
            logger.info(f'Planner agent card: {agent_card}')
        else:
            logger.info('Finding agent for task...')
            agent_card = await self.find_agent_for_task()
            logger.info(f'Task agent card: {agent_card}')
        timeout_config = httpx.Timeout(timeout=180.0, read=180.0, write=30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
            logger.info(f"Agent card: {agent_card}")
            logger.info(f"Agent card URL: {agent_card.url if hasattr(agent_card, 'url') else 'No URL found'}")
            client = A2AClient(httpx_client, agent_card)
            logger.info(f"A2AClient methods: {[method for method in dir(client) if not method.startswith('_')]}")

            payload: dict[str, any] = {
                'message': {
                    'role': 'user',
                    'parts': [{'kind': 'text', 'text': query}],
                    'messageId': task_id,
                    'contextId': context_id
                }
            }
            request = SendStreamingMessageRequest(
                id=str(uuid4()), params=MessageSendParams(**payload)
            )
            # Try to find the correct method name
            available_methods = [method for method in dir(client) if 'send' in method.lower() or 'stream' in method.lower()]
            logger.info(f"Available send/stream methods: {available_methods}")
            
            # Try common method names
            response_stream = None
            if hasattr(client, 'send_message_stream'):
                response_stream = client.send_message_stream(request)
            elif hasattr(client, 'send_streaming_message'):
                response_stream = client.send_streaming_message(request)
            elif hasattr(client, 'stream_message'):
                response_stream = client.stream_message(request)
            elif hasattr(client, 'send_message'):
                response_stream = client.send_message(request)
            else:
                logger.error(f"No suitable streaming method found. Available methods: {dir(client)}")
                raise AttributeError("No suitable streaming method found in A2AClient")
            
            # Check if response_stream is a coroutine or async iterator
            import inspect
            if inspect.iscoroutine(response_stream):
                logger.info("Response is a coroutine, awaiting it...")
                response = await response_stream
                # If it's a single response, yield it and return
                if hasattr(response, 'root'):
                    yield response
                    return
                else:
                    logger.error(f"Unexpected response type: {type(response)}")
                    return
            elif hasattr(response_stream, '__aiter__'):
                logger.info("Response is an async iterator, iterating...")
                async for chunk in response_stream:
                    if isinstance(
                        chunk.root,
                        SendStreamingMessageSuccessResponse,
                    ) and (isinstance(chunk.root.result, TaskArtifactUpdateEvent)):
                        artifact = chunk.root.result.artifact
                        self.result = artifact
                    yield chunk
            else:
                logger.error(f"Response stream is neither coroutine nor async iterator: {type(response_stream)}")
                return

class WorkflowGraph:
    """Representation of Graph for a workflow node"""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes = {}
        self.lates_node = None
        self.node_type = None
        self.state = Status.INITIALIZED
        self.pused_node_id = None

    def add_node(self, node) -> None:
        logger.info(f'Adding Node {node.id}')
        self.nodes[node.id] = node
        self.lates_node = node.id
        self.graph.add_node(node.id, query=node.task)

    def add_edge(self, from_node_id: str, to_node_id: str)  -> None:
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            raise ValueError('Invalid Node IDs')
        self.graph.add_edge(from_node_id, to_node_id)
    
    async def run_workflow(
        self, start_node_id: str = None
    ) -> AsyncIterable[dict[str, any]]:
        logger.info('Running Workflow')
        if not start_node_id or start_node_id not in self.nodes:
            start_nodes = [n for n, d in self.graph.in_degree() if d == 0]
        else:
            start_nodes = [self.nodes[start_node_id].id]
        
        applicable_graph = set()

        for node_id in start_nodes:
            applicable_graph.add(node_id)
            applicable_graph.update(nx.descendants(self.graph, node_id))

        complete_graph = list(nx.topological_sort(self.graph))
        sub_graph = [n for n in complete_graph if n in applicable_graph]
        self.state = Status.RUNNING
        for node_id in sub_graph:
            node = self.nodes[node_id]
            node.state = self.state.RUNNING
            node_attrs = self.graph.nodes[node_id]
            query = node_attrs.get('query', '')
            task_id = node_attrs.get('task_id', '')
            context_id = node_attrs.get('context_id', '')

            async for chunk in node.run_node(query, task_id, context_id):
                if node.state != Status.PAUSED:
                    if isinstance(
                        chunk.root, SendStreamingMessageSuccessResponse
                    )and (
                        isinstance(chunk.root.result, TaskStatusUpdateEvent)
                    ):
                        task_status_event = chunk.root.result
                        context_id = task_status_event.contextId
                        if(
                            task_status_event.status.state
                            == TaskState.input_required
                            and context_id
                        ):
                            node_state = Status.PAUSED
                            self.state = Status.PAUSED
                            self.paused_node_id = node.id
                    yield chunk
            if self.state == Status.PAUSED:
                break
            if self.state == Status.RUNNING:
                node.state = Status.COMPLETED
        if self.state == Status.RUNNING:
            self.state = Status.COMPLETED

    def set_node_attribute(self, node_id, attribute, value):
        nx.set_node_attributes(self.graph, {node_id: value}, attribute)

    def set_node_attributes(self, node_id, attr_val):
        nx.set_node_attributes(self.graph, {node_id: attr_val})

    def is_empty(self) -> bool:
        return self.graph.number_of_nodes() == 0

