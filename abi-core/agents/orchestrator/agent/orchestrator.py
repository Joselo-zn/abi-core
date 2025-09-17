import json
import logging
import os

from collections.abc import AsyncIterable

from a2a.types import (
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
from common import prompts
from common.workflow import Status, WorkflowGraph, WorkflowNode
from agent.agent import AbiAgent

from langchain_community.chat_models import ChatOllama
from langchain.schema.messages import HumanMessage

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv('MODEL_NAME', 'tinyllama:latest')


class AbiOrchestratorAgent(AbiAgent):
    """Orchestrator Agent for coordinating other agents using LangChain as LLM."""

    def __init__(self):
        super().__init__(
            agent_name='Abi Orchestrator Agent',
            description='Facilitate inter agent communication',
            content_types=['text', 'text/plain'],
        )
        self.graph = None
        self.results = []
        self.query_context = {}
        self.query_history = []
        self.context_id = None

        # Initialize LangChain LLM (can be OpenAI, Ollama, etc.)
        self.abi_orchestrator = ChatOllama(model_name=MODEL_NAME, temperature=0.0)
        logger.info(f'[🚀] Starting ABI Orchestrator Agent')

    async def generate_summary(self) -> str:
        """Generate a summary from current results using LangChain LLM."""
        prompt = prompts.ORCHESTRATOR_COT_INSTRUCTIONS.replace(
            '{task_data}', str(self.results)
        )
        response = await self.abi_orchestrator.ainvoke([HumanMessage(content=prompt)])
        return response.content

    def answer_user_question(self, question) -> str:
            try:
                self.abi_orchestrator = ChatOllama(
                    model_name=MODEL_NAME,
                    temperature=0.0,
                    response_format="json"
                )
                prompt = prompts.QA_COT_PROMPT.replace(
                        '{CONTEXT_JSON}', str(self.query_context)
                    ).replace(
                         '{CONVERSATION_HISTORY}', str(self.query_history)
                         ).replace('{USER_QUESTION}', question)
                response = self.abi_orchestrator.ainvoke([HumanMessage(
                    contents=prompt)])
                return response.text
            except Exception as e:
                logger.info(f'Error answering user question: {e}')
            return '{"can_answer": "no", "answer": "Cannot answer based on provided context"}'

    def set_node_attributes(
        self, node_id, task_id=None, context_id=None, query=None
    ):
        """Pack and Setting the Attributes for the node"""
        attr_val = {}
        if task_id:
            attr_val['task_id'] = task_id
        if context_id:
            attr_val['context_id'] = context_id
        if query:
            attr_val['query'] = query

        self.graph.set_node_attributes(node_id, attr_val)

    def add_graph_node(
        self,
        task_id,
        context_id,
        query: str,
        node_id: str = None,
        node_key: str = None,
        node_label: str = None
    ) -> WorkflowNode:
        """Adding Node to the workflow"""
        node = WorkflowNode(task=query, node_key=node_key, node_label=node_label)
        self.graph.add_node(node)
        if node_id:
            self.graph.add_edge(node_id, node.id)
        self.set_node_attribute(node.id, task_id, context_id, query)
        
        return node

    def clear_state(self):
        self.graph = None
        self.results.clear()
        self.query_context.clear()
        self.query_history.clear()

    async def stream(self, query, context_id, task_id) -> AsyncIterable[dict[str, any]]:
        """Executes and Streams Response"""
        logger.info(f'[*] Running {self.agent_name} stream {context_id}, task {task_id} - {query} ')
        if not query:
            raise ValueError('Please provide a Query')
        if self.context_id != context_id:
            self.clear_state()
            self.context_id = context_id
        self.query_history.append(query)
        start_node_id = None

        if not self.graph:
            self.graph = WorkflowGraph()
            planner_node = self.add_graph_node(
                task_id=task_id,
                context_id=context_id,
                query=query,
                node_key='planner',
                node_label='Planner'
            )
            start_node_id = planner_node.id
        elif self.graph.state == Status.PAUSED:
            start_node_id = self.graph.pused_node_id
            self.set_node_attributes(node_id=start_node_id, query=query)
        
        while True:
            self.set_node_attributes(
                node_id=start_node_id,
                task_id=task_id,
                context_id=context_id
            )
            resume_workflow = False
            async for chunk in self.graph.run_workflow(
                start_node_id=start_node_id
            ):
                if isinstance(chunk.root, SendStreamingMessageSuccessResponse):
                    if isinstance(chunk.root.result, TaskStatusUpdateEvent):
                        task_status_event = chunk.root.result
                        context_id = task_status_event.context_id
                        if(
                            task_status_event.status.state == TaskState.completed and context_id
                        ):
                            yield {
                                "event": "completed",
                                "node": start_node_id,
                                "context": context_id,
                            }
                            continue
                        if (
                            task_status_event.status.state == TaskState.input_required
                        ):
                            question = task_status_event.status.message.parts[0].root.text
                            try:
                                answer = json.loads(self.answer_user_question(question))
                                logger.info(f'[*] Agent Answer {answer}')
                                if answer['can_answer'] == 'yes':
                                    query = answer['answer']
                                    start_node_id = self.graph.paused_node_id
                                    self.set_node_attributes(
                                        node_id=start_node_id,
                                        query=query
                                    )
                                    resume_workflow = True
                            except Exception:
                                logger.info('Error converting answer data')
                    if isinstance(chunk.root.result, TaskArtifactUpdateEvent):
                        artifact = chunk.root.result.artifact    
                        self.results.append(artifact)
                        if artifact.name == 'PlannerAgent-result':
                            artifact_data = artifact.parts[0].root.data
                            if 'data_info' in artifact_data:
                                self.query_context = artifact_data['data_info']
                                logger.info(
                                    f'Updating workflow with {len(artifact_data["task"])} task nodes'
                                    )
                                current_node_id = start_node_id
                                for idx, task_data in enumerate(artifact_data['task']):
                                    node = self.add_graph_node(
                                        task_id=task_id,
                                        context_id=context_id,
                                        query=task_data['description'],
                                        node_id=current_node_id
                                    )
                                    current_node_id = node.id

                                    if idx == 0:
                                        resume_workflow = True
                                        start_node_id = node.id
                        else:
                            #@TODO Review this part for further implementation
                            # Not planner but artifacts from other tasks,
                            # continue to the next node in the workflow.
                            # client does not get the artifact,
                            # a summary is shown at the end of the workflow.
                            continue

                if not resume_workflow:
                    logger.info('No workflow resume detected, yielding chunk')
                    yield chunk
            if not resume_workflow:
                logger.info(
                        'Workflow iteration complete and no restart requested. Exiting main loop.'
                    )
                break
            else:
                logger.info('Restarting workflow loop.')
        if  self.graph.state == Status.COMPLETED:
            logger.info(f'Generating summary for {len(self.results)} results')
            summary = await self.generate_summary()
            self.clear_state()
            logger.info(f'Summary: {summary}')
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': summary,
            }
