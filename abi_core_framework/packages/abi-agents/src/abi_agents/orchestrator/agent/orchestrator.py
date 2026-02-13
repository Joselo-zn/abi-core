import json
import logging
from collections.abc import AsyncIterable

from a2a.types import (
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)

from abi_core.common import prompts
from abi_core.common.utils import abi_logging
from abi_core.common.workflow import Status, WorkflowGraph, WorkflowNode
from abi_core.common.semantic_tools import tool_find_agent
from abi_core.agent.agent import AbiAgent

from langchain_ollama import ChatOllama
from langchain.agents import create_agent

from a2a.types import AgentCard

# Import configuration
from config import config, AGENT_CARD 

logger = logging.getLogger(__name__)


class AbiOrchestratorAgent(AbiAgent):
    """Orchestrator Agent - coordinates multi-agent workflows using LangGraph"""

    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            content_types=['text', 'text/plain'],
        )
        
        # Initialize LLM
        self.llm = ChatOllama(
            model=config.MODEL_NAME,
            base_url=config.OLLAMA_HOST,
            temperature=0.1
        )
        
        abi_logging(f'[✅] LLM initialized: {config.MODEL_NAME} at {config.OLLAMA_HOST}')
        
        # Create agent with tools
        self.agent = create_agent(
            model=self.llm,
            tools=[tool_find_agent],
            system_prompt=prompts.ORCHESTRATOR_COT_INSTRUCTIONS
        )
        
        abi_logging(f'[🚀] Starting ABI {config.AGENT_DISPLAY_NAME}')

    def extract_plan_from_results(self, results: list) -> dict | None:
        """Extract plan JSON from Planner results"""
        for result in results:
            try:
                abi_logging(f"[🔍] Extracting plan from result type: {type(result)}")
                
                # El objeto tiene root=SendMessageSuccessResponse
                if hasattr(result, 'root'):
                    response = result.root  # SendMessageSuccessResponse
                    
                    if hasattr(response, 'result'):
                        task = response.result  # Task
                        
                        if hasattr(task, 'artifacts'):
                            for artifact in task.artifacts:
                                if hasattr(artifact, 'parts'):
                                    for part in artifact.parts:
                                        # Part tiene root=DataPart
                                        if hasattr(part, 'root'):
                                            data_part = part.root
                                            if hasattr(data_part, 'data') and isinstance(data_part.data, dict):
                                                if 'tasks' in data_part.data:
                                                    abi_logging(f"[✅] Plan extracted successfully")
                                                    return data_part.data
                                        
                                        # Fallback: intentar con text
                                        elif hasattr(part, 'text'):
                                            try:
                                                data = json.loads(part.text)
                                                if isinstance(data, dict) and 'tasks' in data:
                                                    return data
                                            except:
                                                pass
                                                
            except Exception as e:
                abi_logging(f"[⚠️] Error extracting plan: {e}")
                continue
        
        return None
    
    def check_for_clarification(self, results: list) -> tuple[bool, str | None]:
        """
        Check if Planner is requesting clarification
        
        Returns:
            Tuple of (needs_clarification, clarification_message)
        """
        for result in results:
            try:
                if hasattr(result, 'root'):
                    response = result.root
                    
                    # Check for input_required status
                    if hasattr(response, 'result'):
                        task = response.result
                        
                        # Check task status
                        if hasattr(task, 'status') and hasattr(task.status, 'state'):
                            # Check if state is input_required (can be string or enum)
                            state = task.status.state
                            state_str = str(state).lower() if hasattr(state, 'value') else str(state).lower()
                            
                            if 'input' in state_str and 'required' in state_str:
                                abi_logging("[❓] Planner requires clarification")
                                
                                # Extract clarification message from status.message.parts
                                if hasattr(task.status, 'message') and hasattr(task.status.message, 'parts'):
                                    for part in task.status.message.parts:
                                        if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                            abi_logging(f"[✅] Clarification message extracted")
                                            return True, part.root.text
                                        elif hasattr(part, 'text'):
                                            return True, part.text
                                
                                return True, "Planner requires clarification (no message found)"
                                                
            except Exception as e:
                abi_logging(f"[⚠️] Error checking clarification: {e}")
                continue
        
        return False, None

    async def create_workflow_from_plan(self, plan: dict, context_id: str, task_id: str) -> WorkflowGraph:
        """Create WorkflowGraph from Planner's plan"""
        workflow = WorkflowGraph()
        nodes = {}
        tasks = plan.get('tasks', [])
        
        abi_logging(f"[🔨] Creating workflow with {len(tasks)} tasks")
        
        # Create nodes with assigned agents
        for task in tasks:
            task_id_key = task.get('task_id')
            description = task.get('description', '')
            agents = task.get('agents', [])
            
            # Get AgentCard from Planner's assignment
            if not agents or not agents[0]:
                abi_logging(f"[⚠️] Task {task_id_key} has no agent assigned")
                continue
            
            # Convert dict to AgentCard if needed
            agent_dict = agents[0]
            target_agent_card = AgentCard(**agent_dict) if isinstance(agent_dict, dict) else agent_dict
            
            node = WorkflowNode(
                task=description,
                source_agent_card=AGENT_CARD,
                target_agent_card=target_agent_card,
                node_key=task_id_key,
                node_label=f"{task_id_key}: {description[:40]}"
            )
            
            workflow.add_node(node)
            nodes[task_id_key] = node
            
            workflow.set_node_attributes(node.id, {
                'task_id': task_id,
                'context_id': context_id,
                'query': description
            })
        
        # Create edges from dependencies
        for task in tasks:
            task_id_key = task.get('task_id')
            dependencies = task.get('dependencies', [])
            
            for dep in dependencies:
                if dep in nodes and task_id_key in nodes:
                    workflow.add_edge(nodes[dep].id, nodes[task_id_key].id)
                    abi_logging(f"[🔗] Edge: {dep} → {task_id_key}")
        
        # Set source card for A2A validation
        workflow.set_source_card(AGENT_CARD)
        
        return workflow

    async def call_planner(self, query: str, context_id: str, task_id: str) -> list:
        """Call Planner and return results"""
        abi_logging(f"[📞] Calling Planner: {query}")
        
        # Use tool_find_agent to get Planner
        planner_agent_card = await tool_find_agent.ainvoke({"query": "planner"})
        
        if not planner_agent_card:
            raise ValueError("Could not find Planner agent")
        
        # Create workflow with planner node
        workflow = WorkflowGraph()
        planner_node = WorkflowNode(
            task=query,
            source_agent_card=AGENT_CARD,
            target_agent_card=planner_agent_card,
            node_key='planner',
            node_label='Planning Phase'
        )
        workflow.add_node(planner_node)
        workflow.set_node_attributes(planner_node.id, {
            'context_id': context_id,
            'task_id': task_id,
            'query': query
        })
        
        # Set source card for A2A validation
        workflow.set_source_card(AGENT_CARD)
        
        results = []
        async for chunk in workflow.run_workflow():
            results.append(chunk)
        
        return results

    async def stream(self, query: str, context_id: str, task_id: str) -> AsyncIterable[dict[str, any]]:
        """Main entry point - orchestrate workflow execution using LangGraph"""
        
        abi_logging(f'[*] Orchestrator stream - context: {context_id}, task: {task_id}')
        abi_logging(f'[📝] Query: {query}')
        
        if not query:
            raise ValueError('Please provide a Query')
        
        try:
            # Step 1: Call Planner
            planner_results = await self.call_planner(query, context_id, task_id)
            
            # Step 1.5: Check if Planner needs clarification
            needs_clarification, clarification_msg = self.check_for_clarification(planner_results)
            
            if needs_clarification:
                abi_logging("[❓] Forwarding clarification request to user")
                
                # Format the clarification message for better readability
                formatted_msg = f"🤔 **Necesito más información para crear el mejor plan:**\n\n{clarification_msg}"
                
                yield {
                    'response_type': 'text',
                    'is_task_completed': False,
                    'requires_input': True,
                    'content': formatted_msg
                }
                return
            
            # Step 2: Extract plan
            plan = self.extract_plan_from_results(planner_results)
            
            if not plan:
                yield {
                    'response_type': 'text',
                    'is_task_completed': True,
                    'content': "❌ Could not generate execution plan"
                }
                return
            
            abi_logging(f"[📋] Plan received with {len(plan.get('tasks', []))} tasks")
            
            # Step 3: Create and execute workflow using LangGraph
            workflow = await self.create_workflow_from_plan(plan, context_id, task_id)
            
            # Step 4: Stream workflow execution (LangGraph handles state)
            results = []
            async for chunk in workflow.run_workflow():
                results.append(chunk)
                yield chunk
            
            # Step 5: Synthesize results if completed
            if workflow.state == Status.COMPLETED:
                abi_logging(f"[✅] Workflow completed with {len(results)} results")
                
                # Use agent to synthesize results
                synthesis_query = f"Synthesize the following workflow results:\nPlan: {json.dumps(plan, indent=2)}\nResults count: {len(results)}"
                
                inputs = {"messages": [{"role": "user", "content": synthesis_query}]}
                
                final_synthesis = None
                async for chunk in self.agent.astream(inputs, stream_mode="updates"):
                    for node_name, node_data in chunk.items():
                        if "messages" in node_data:
                            for msg in node_data["messages"]:
                                if hasattr(msg, 'content') and msg.content:
                                    final_synthesis = msg.content
                
                yield {
                    'response_type': 'text',
                    'is_task_completed': True,
                    'content': final_synthesis or "Workflow completed successfully"
                }
            
        except Exception as e:
            abi_logging(f"[❌] Error in orchestration: {e}")
            yield {
                'response_type': 'text',
                'is_task_completed': True,
                'content': f"❌ Error: {str(e)}"
            }
