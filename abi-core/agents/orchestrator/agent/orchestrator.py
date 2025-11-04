import json
import logging
import os

from collections.abc import AsyncIterable

from a2a.types import (
    SendStreamingMessageSuccessResponse,
    SendMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    Task,
    TaskStatusUpdateEvent,
)

from common import prompts
from common.utils import abi_logging
from common.workflow import Status, WorkflowGraph, WorkflowNode
from agent.agent import AbiAgent
from .models.outputs_model import QAResult

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage


logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv('MODEL_NAME', 'llama3.2:3b')


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
        self.abi_orchestrator = ChatOllama(model=MODEL_NAME, temperature=0.1)
        abi_logging(f'[🚀] Starting ABI {self.agent_name}')

    def _router_from_qa(self, class_type):
        if class_type == "methodology":
            return {"flow": "orchestrator_answer",
                    "next": "fill_analysis_approach_defaults"}
        if class_type == "static_knowledge":
            return {"flow": "worker_semantic",
                    "task": {"op": "semantic_summarize",
                            "top_k": 8}}
        if class_type == "time_sensitive":
            return {"flow": "planner_tool",
                    "tool_request": {
                        "tool": "web.search",
                        "policy": "default"
                    }}

        return {"flow": "orchestrator_answer",
                "next": "fill_analysis_approach_defaults"}

    async def _execute_flow_as_node(self, route, question, task_id, context_id):
        """Genera nodo dinámico basado en el routing y lo agrega al workflow"""
        flow_type = route["flow"]
        
        # Construir query específico para el tipo de flujo
        query = self._build_query_for_flow(route, question)
        abi_logging(f'QUERY {query}')
        # Crear nodo dinámico en el workflow
        dynamic_node = self.add_graph_node(
            task_id=task_id,
            context_id=context_id,
            query=query,
            node_id=None,  # Se conectará automáticamente
            node_key='',
            node_label=self._get_node_label(flow_type)
        )
        resume_workflow = True
        abi_logging(f'Created dynamic node {dynamic_node.id} for flow {flow_type}')
        return dynamic_node.id

    def _build_query_for_flow(self, route, question):
        """Construye query específico según el tipo de flujo"""
        flow_type = route["flow"]
        abi_logging(f'FLOW TYPE {flow_type}, ROUTE {route}, QUESTION {question}')
        if flow_type == "orchestrator_answer":
            return f"Answer using methodology approach: {question}"
        elif flow_type == "worker_semantic":
            task = route.get("task", {})
            top_k = task.get("top_k", 8)
            return f"semantic_search: {question} top_k={top_k}"
        elif flow_type == "planner_tool":
            tool_req = route.get("tool_request", {})
            tool = tool_req.get("tool", "web.search")
            return f"execute_tool: {tool} query={question}"
        else:
            return f"process: {question}"

    def _get_node_label(self, flow_type):
        """Retorna label legible para el nodo"""
        labels = {
            "orchestrator_answer": "Direct Answer",
            "worker_semantic": "Semantic Search", 
            "planner_tool": "External Tool"
        }
        return labels.get(flow_type, "Unknown Flow")

    async def generate_summary(self) -> str:
        """Generate a summary from current results using LangChain LLM."""
        prompt = prompts.ORCHESTRATOR_COT_INSTRUCTIONS.replace(
            '{task_data}', str(self.results)
        )
        response = await self.abi_orchestrator.ainvoke([HumanMessage(content=prompt)])
        return response.content

    async def answer_planner_question(self, question, context, context_id, task_id) -> str:
        try:
            prompt = prompts.ORCHESTRATOR_QA_COT_PLANNER.replace('{query}', question)
            classify = await self.abi_orchestrator.ainvoke([HumanMessage(content=prompt)])
            
            validated_classify = QAResult.model_validate_json(classify.content)
            route = self._router_from_qa(validated_classify.class_)
            
            # Generar nodo dinámico basado en el routing
            dynamic_node_id = await self._execute_flow_as_node(route, question, task_id, context_id)
            
            return json.dumps({
                "can_answer": "yes", 
                "answer": f"Executing {route['flow']} workflow",
                "node_id": dynamic_node_id
            })
        
        except Exception as e:
            abi_logging(f'Error answering planner question: {e}')
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
        self.set_node_attributes(node.id, task_id, context_id, query)
        
        return node

    def clear_state(self):
        self.graph = None
        self.results.clear()
        self.query_context.clear()
        self.query_history.clear()

    async def stream(self, query, context_id, task_id) -> AsyncIterable[dict[str, any]]:
        """Executes and Streams Response"""
        abi_logging(f'[*] Running {self.agent_name} stream {context_id}, task {task_id} - {query} ')
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
                abi_logging(f'CHUNK ROOT: {type(chunk.root)}', 'debug')
                if isinstance(chunk.root, SendMessageSuccessResponse):
                    abi_logging(f'isinstance chunk.root.result: {isinstance(chunk.root.result, TaskStatusUpdateEvent)}','debug')
                    abi_logging(f'TYPE of chunk.root.result: {type(chunk.root.result)}', 'debug')
                    abi_logging(f'DIR of chunk.root.result: {dir(chunk.root.result)}', 'debug')
                    abi_logging(f' CHUNK ROOT RESUL {chunk.root.result}')
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
                                answer = json.loads(await self.answer_planner_question(question, {}, context_id, task_id))
                                abi_logging(f'[*] Agent Answer {answer}')
                                if answer['can_answer'] == 'yes':
                                    query = answer['answer']
                                    start_node_id = self.graph.paused_node_id
                                    self.set_node_attributes(
                                        node_id=start_node_id,
                                        query=query
                                    )
                                    resume_workflow = True
                            except Exception:
                                abi_logging('Error converting answer data')
                    abi_logging(f"CHUNK ROOT RESULTO para artifacts: {type(chunk.root.result)}")
                    abi_logging(f"CHUNK ROOT RESULTO para artifacts: {chunk.root.result}")
                    if isinstance(chunk.root.result, TaskArtifactUpdateEvent):
                        artifact = chunk.root.result.artifact    
                        self.results.append(artifact)
                        if artifact.name == 'PlannerAgent-result':
                            artifact_data = artifact.parts[0].root.data
                            if 'data_info' in artifact_data:
                                self.query_context = artifact_data['data_info']
                                abi_logging(
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
                    elif isinstance(chunk.root.result, Task):
                        task_status_event = chunk.root.result
                        if task_status_event.status.state == TaskState.input_required:
                            abi_logging(f'task_status_event.status {dir(task_status_event.status)}')
                            question = task_status_event.status.message.parts[0].root.text
                            context_id = task_status_event.context_id
                            context = task_status_event.status.message
                            try:
                                abi_logging(f"Agent question {question}")
                                agent_answer = await self.answer_planner_question(question, {}, context_id, task_id)
                                json_answer = json.loads(agent_answer)
                                abi_logging(f'[*] Agent Answer {json_answer}')

                                if json_answer['can_answer'] == 'yes':
                                    query = json_answer['answer']
                                    start_node_id = self.graph.paused_node_id
                                    self.set_node_attributes(
                                        node_id=start_node_id,
                                        query=query
                                    )
                                    resume_workflow = True
                            except Exception:
                                abi_logging('Error converting answer data')
                if not resume_workflow:
                    abi_logging('No workflow resume detected, yielding chunk')
                    yield chunk
            if not resume_workflow:
                abi_logging(
                        'Workflow iteration complete and no restart requested. Exiting main loop.'
                    )
                break
            else:
                abi_logging('Restarting workflow loop.')
        if  self.graph.state == Status.COMPLETED:
            abi_logging(f'Generating summary for {len(self.results)} results')
            summary = await self.generate_summary()
            self.clear_state()
            abi_logging(f'Summary: {summary}')
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': summary,
            }
