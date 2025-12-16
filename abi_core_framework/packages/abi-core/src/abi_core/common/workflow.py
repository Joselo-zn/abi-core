import json
import uuid
import logging

from collections.abc import AsyncIterable
from enum import Enum
from typing import TypedDict, Annotated, Sequence
from uuid import uuid4

import httpx

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from a2a.client import A2AClient
from abi_core.common.utils import get_mcp_server_config
from abi_core.abi_mcp import client
from abi_core.common.abi_a2a import agent_connection

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
    such as finding an Agent Capabilities. It manages its own state
    and can execute its assigned task.
    
    Supports:
    - Task execution with assigned agents
    - Q&A flow for clarification
    - Health checks and retries
    - Result collection
    """

    def __init__(
        self,
        task: str,
        source_agent_card: AgentCard,
        target_agent_card: AgentCard,
        node_key: str | None = None,
        node_label: str | None = None,
        requires_clarification: bool = False,
        max_retries: int = 5,
    ):
        self.id = str(uuid.uuid4())
        self.node_key = node_key
        self.node_label = node_label
        self.task = task
        self.target_agent_card = target_agent_card  # AgentCard to execute (required)
        self.requires_clarification = requires_clarification
        self.max_retries = max_retries
        self.result = None
        self.state = Status.READY
        self.clarification_questions = []
        self.clarification_answers = {}
        self.retry_count = 0

    async def run_node(
        self,
        query: str,
        task_id: str,
        context_id: str,
        source_card: AgentCard,
    ) -> AsyncIterable[dict[str, any]]:
        """Execute node with assigned agent - does NOT search for agents"""
        logger.info(f'Execute node {self.id} with agent {self.target_agent_card.name}')
        
        if not self.target_agent_card:
            raise ValueError(f"Node {self.id} has no agent assigned")
        
        payload: dict[str, any] = {
            'message': {
                'role': 'user',
                'parts': [{'kind': 'text', 'text': query}],
                'messageId': task_id,
                'contextId': context_id
            }
        }

        # Pass both source and target cards for A2A validation
        async for chunk in agent_connection(source_card, self.target_agent_card, payload):
            yield chunk
        

class WorkflowState(TypedDict):
    """State for LangGraph workflow"""
    current_node_id: str
    completed_nodes: list[str]
    paused_node_id: str | None
    status: str
    context_id: str
    task_id: str
    results: dict[str, any]


class WorkflowGraph:
    """Representation of Graph for a workflow node using LangGraph"""

    def __init__(self):
        self.graph_builder = StateGraph(WorkflowState)
        self.nodes = {}
        self.latest_node = None
        self.node_type = None
        self.state = Status.INITIALIZED
        self.paused_node_id = None
        self.compiled_graph = None
        self._node_attributes = {}  # Store node attributes

    def add_node(self, node) -> None:
        """Add a node to the workflow graph"""
        logger.info(f'Adding Node {node.id}')
        self.nodes[node.id] = node
        self.latest_node = node.id
        
        # Store node attributes
        self._node_attributes[node.id] = {
            'query': node.task,
            'task_id': '',
            'context_id': ''
        }
        
        # Create node function for LangGraph
        async def node_function(state: WorkflowState):
            """Execute this workflow node"""
            logger.info(f'Executing node {node.id}')
            node.state = Status.RUNNING
            
            # Get attributes
            attrs = self._node_attributes.get(node.id, {})
            query = attrs.get('query', '')
            task_id = attrs.get('task_id', state.get('task_id', ''))
            context_id = attrs.get('context_id', state.get('context_id', ''))
            
            # Run node and collect results
            # Note: source_card should be passed from the orchestrator/caller
            # For now, we'll need to get it from state or context
            source_card = attrs.get('source_card')
            if not source_card:
                # This should be set by the orchestrator when creating the workflow
                raise ValueError("source_card not provided in node attributes")
            
            results = []
            async for chunk in node.run_node(query, task_id, context_id, source_card):
                results.append(chunk)
                
                # Check for pause condition
                if isinstance(chunk.root, SendStreamingMessageSuccessResponse) and \
                   isinstance(chunk.root.result, TaskStatusUpdateEvent):
                    task_status_event = chunk.root.result
                    if task_status_event.status.state == TaskState.input_required:
                        node.state = Status.PAUSED
                        return {
                            **state,
                            'status': Status.PAUSED.value,
                            'paused_node_id': node.id,
                            'context_id': task_status_event.contextId,
                            'results': {**state.get('results', {}), node.id: results}
                        }
            
            # Node completed
            node.state = Status.COMPLETED
            completed = state.get('completed_nodes', []) + [node.id]
            
            return {
                **state,
                'completed_nodes': completed,
                'current_node_id': node.id,
                'results': {**state.get('results', {}), node.id: results}
            }
        
        # Add node to LangGraph
        self.graph_builder.add_node(node.id, node_function)

    def add_edge(self, from_node_id: str, to_node_id: str) -> None:
        """Add an edge between two nodes"""
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            raise ValueError('Invalid Node IDs')
        
        logger.info(f'Adding edge from {from_node_id} to {to_node_id}')
        
        # Track edges for later use
        if not hasattr(self, '_edges'):
            self._edges = []
        self._edges.append((from_node_id, to_node_id))
        
        self.graph_builder.add_edge(from_node_id, to_node_id)
    
    def compile(self):
        """Compile the LangGraph"""
        if not self.compiled_graph:
            # Set entry point (first node with no incoming edges)
            entry_nodes = [
                node_id for node_id in self.nodes.keys()
                if not any(node_id == to_id for _, to_id in self._get_edges())
            ]
            
            if entry_nodes:
                self.graph_builder.set_entry_point(entry_nodes[0])
            
            # Set finish points (nodes with no outgoing edges)
            finish_nodes = [
                node_id for node_id in self.nodes.keys()
                if not any(node_id == from_id for from_id, _ in self._get_edges())
            ]
            
            for finish_node in finish_nodes:
                self.graph_builder.add_edge(finish_node, END)
            
            self.compiled_graph = self.graph_builder.compile()
        
        return self.compiled_graph
    
    def _get_edges(self):
        """Get all edges from the graph builder"""
        # LangGraph doesn't expose edges directly, so we track them
        if not hasattr(self, '_edges'):
            self._edges = []
        return self._edges
    
    async def run_workflow(
        self, start_node_id: str = None
    ) -> AsyncIterable[dict[str, any]]:
        """Run the workflow using LangGraph"""
        logger.info('Running Workflow with LangGraph')
        
        # Compile graph if not already compiled
        graph = self.compile()
        
        # Initialize state
        initial_state: WorkflowState = {
            'current_node_id': start_node_id or list(self.nodes.keys())[0],
            'completed_nodes': [],
            'paused_node_id': None,
            'status': Status.RUNNING.value,
            'context_id': '',
            'task_id': '',
            'results': {}
        }
        
        self.state = Status.RUNNING
        
        # Stream workflow execution
        async for event in graph.astream(initial_state):
            # Extract node results and yield chunks
            for node_id, node_state in event.items():
                if node_id in self.nodes and 'results' in node_state:
                    node_results = node_state['results'].get(node_id, [])
                    for chunk in node_results:
                        yield chunk
                
                # Check for pause
                if node_state.get('status') == Status.PAUSED.value:
                    self.state = Status.PAUSED
                    self.paused_node_id = node_state.get('paused_node_id')
                    return
        
        # Workflow completed
        self.state = Status.COMPLETED

    def set_node_attribute(self, node_id, attribute, value):
        """Set a single attribute for a node"""
        if node_id not in self._node_attributes:
            self._node_attributes[node_id] = {}
        self._node_attributes[node_id][attribute] = value

    def set_node_attributes(self, node_id, attr_val):
        """Set multiple attributes for a node"""
        if node_id not in self._node_attributes:
            self._node_attributes[node_id] = {}
        self._node_attributes[node_id].update(attr_val)
    
    def set_source_card(self, source_card: AgentCard):
        """Set source card for all nodes (for A2A validation)"""
        for node_id in self.nodes.keys():
            self.set_node_attribute(node_id, 'source_card', source_card)

    def is_empty(self) -> bool:
        """Check if the workflow graph is empty"""
        return len(self.nodes) == 0

