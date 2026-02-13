import logging
import json

from collections.abc import AsyncIterable

from a2a.types import (
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent
)
from abi_core.common import prompts
from abi_core.common.utils import abi_logging
from abi_core.common.semantic_tools import tool_find_agent, tool_recommend_agents
from models.agent_models import PlannerResponse
from abi_core.agent.agent import AbiAgent

from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_core.output_parsers import JsonOutputParser

# Import configuration
from config import config

class AbiPlannerAgent(AbiAgent):
    """Planner divides a big plan into small executable actions/tasks and assigns specific agents"""
    
    def __init__(self):
        super().__init__(
            agent_name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            content_types=['text', 'text/plain']
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
            tools=[tool_find_agent, tool_recommend_agents],
            system_prompt=prompts.PLANNER_COT_INSTRUCTIONS
        )
        
        self.parser = JsonOutputParser()
        self.conversation_history = {}  # Store conversation per session
        
        abi_logging(f'[🚀] Starting ABI {config.AGENT_DISPLAY_NAME}')

    async def decompose_and_assign(self, query: str, session_id: str, user_answers: dict = None) -> dict:
        """
        Decompose query into tasks and assign specific agents.
        
        Returns:
            dict with either:
            - {"status": "needs_clarification", "questions": [...]}
            - {"status": "ready", "plan": {...}}
        """
        
        # Build context from conversation history
        context = self.conversation_history.get(session_id, {})
        if user_answers:
            context.update(user_answers)
            self.conversation_history[session_id] = context
        
        # Use agent to analyze and decompose
        planning_query = f"User request: {query}\nContext: {json.dumps(context, indent=2)}"
        
        inputs = {"messages": [{"role": "user", "content": planning_query}]}
        
        try:
            # Stream agent execution
            final_response = None
            async for chunk in self.agent.astream(inputs, stream_mode="updates"):
                for node_name, node_data in chunk.items():
                    if "messages" in node_data:
                        for msg in node_data["messages"]:
                            if hasattr(msg, 'content') and msg.content:
                                final_response = msg.content
            
            # Clean response: remove double braces that LLM might add
            if final_response:
                # Remove markdown code blocks if present
                final_response = final_response.strip()
                if final_response.startswith('```json'):
                    final_response = final_response[7:]  # Remove ```json
                if final_response.startswith('```'):
                    final_response = final_response[3:]  # Remove ```
                if final_response.endswith('```'):
                    final_response = final_response[:-3]  # Remove trailing ```
                final_response = final_response.strip()
                
                # Replace double braces with single braces
                final_response = final_response.replace('{{', '{').replace('}}', '}')
                
                abi_logging(f"[🔍] Cleaned response for parsing")
            
            # Parse response
            plan_data = self.parser.parse(final_response) if final_response else {}
            
            # Check if needs clarification
            if plan_data.get('status') == 'needs_clarification':
                abi_logging(f"[❓] Planner needs clarification: {len(plan_data.get('questions', []))} questions")
                return plan_data
            
            # Step 2: Assign agents to each task
            if plan_data.get('status') == 'ready':
                plan = plan_data.get('plan', {})
                tasks = plan.get('tasks', [])
                
                abi_logging(f"[🔍] Assigning agents to {len(tasks)} tasks...")
                
                for task in tasks:
                    task_desc = task.get('description', '')
                    agent_count = task.get('agent_count', 1)
                    
                    # Find and assign agents
                    if agent_count == 1:
                        agent = await tool_find_agent.ainvoke(task_desc)
                        if not agent:
                            # Fallback to recommendations
                            recommendations = await tool_recommend_agents(task_desc, max_agents=1)
                            # recommendations is a list of dicts with agent info
                            agent_data = recommendations[0] if recommendations else None
                        else:
                            # agent is an AgentCard object
                            agent_data = agent.dict() if hasattr(agent, 'dict') else agent
                        
                        task['agents'] = [agent_data] if agent_data else []
                    else:
                        # Multiple agents needed
                        recommendations = await tool_recommend_agents(task_desc, max_agents=agent_count)
                        # recommendations is already a list of agent dicts
                        task['agents'] = recommendations if recommendations else []
                    
                    abi_logging(f"[✅] Task '{task['task_id']}': {len(task['agents'])} agent(s) assigned")
                
                return plan_data
            
        except json.JSONDecodeError as e:
            abi_logging(f"[❌] Error parsing LLM response: {e}")
            # Fallback: simple single-task plan
            return {
                "status": "ready",
                "plan": {
                    "objective": query,
                    "tasks": [{
                        "task_id": "task_1",
                        "description": query,
                        "agents": [],
                        "agent_count": 1,
                        "dependencies": [],
                        "requires_clarification": False
                    }],
                    "execution_strategy": "sequential"
                }
            }
        except Exception as e:
            abi_logging(f"[❌] Error in decompose_and_assign: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def stream(
        self, query, session_id, task_id
    ) -> AsyncIterable[dict[str, any]]:
        """Stream planning process with Q&A support"""
        
        abi_logging(f'[*] Running Planner stream session {session_id} task {task_id}')
        abi_logging(f'[📝] Query: {query}')
        
        # Check if this is an answer to a previous question
        user_answers = None
        if session_id in self.conversation_history:
            # This might be an answer, extract it
            # Format expected: "answer_id: answer_text"
            if ':' in query:
                parts = query.split(':', 1)
                answer_id = parts[0].strip()
                answer_text = parts[1].strip()
                user_answers = {answer_id: answer_text}
                abi_logging(f'[💬] Received answer for {answer_id}: {answer_text}')
        
        # Decompose and assign agents
        result = await self.decompose_and_assign(query, session_id, user_answers)
        
        if result.get('status') == 'needs_clarification':
            # Need to ask user questions
            questions = result.get('questions', [])
            partial = result.get('partial_understanding', '')
            
            abi_logging(f"[❓] Need clarification: {len(questions)} questions")
            
            # Format questions for user
            question_text = f"I need some clarification to create the best plan:\n\n"
            question_text += f"What I understand so far: {partial}\n\n"
            question_text += "Questions:\n"
            
            for i, q in enumerate(questions, 1):
                q_id = q.get('id', f'q{i}')
                q_text = q.get('question', '')
                q_type = q.get('type', 'required')
                options = q.get('options', [])
                
                question_text += f"{i}. [{q_type.upper()}] {q_text}\n"
                if options:
                    question_text += f"   Options: {', '.join(options)}\n"
                question_text += f"   (Answer with: {q_id}: your answer)\n\n"
            
            yield {
                'response_type': 'text',
                'is_task_completed': False,
                'require_user_input': True,
                'content': question_text,
                'metadata': {
                    'status': 'needs_clarification',
                    'questions': questions
                }
            }
            
        elif result.get('status') == 'ready':
            # Plan is ready
            plan = result.get('plan', {})
            
            abi_logging(f"[✅] Plan ready with {len(plan.get('tasks', []))} tasks")
            
            # Send plan summary
            summary = self._format_plan_summary(plan)
            
            yield {
                'response_type': 'text',
                'is_task_completed': False,
                'require_user_input': False,
                'content': summary
            }
            
            # Send complete plan data
            yield {
                'response_type': 'data',
                'is_task_completed': True,
                'require_user_input': False,
                'content': plan,
                'metadata': {
                    'status': 'ready',
                    'task_count': len(plan.get('tasks', [])),
                    'execution_strategy': plan.get('execution_strategy', 'sequential')
                }
            }
            
        else:
            # Error
            error_msg = result.get('message', 'Unknown error occurred')
            abi_logging(f"[❌] Planning error: {error_msg}")
            
            yield {
                'response_type': 'text',
                'is_task_completed': True,
                'require_user_input': False,
                'content': f"Error creating plan: {error_msg}"
            }
    
    def _format_plan_summary(self, plan: dict) -> str:
        """Format plan into human-readable summary"""
        
        objective = plan.get('objective', 'Complete user request')
        tasks = plan.get('tasks', [])
        strategy = plan.get('execution_strategy', 'sequential')
        
        summary = f"📋 **Plan Created**\n\n"
        summary += f"🎯 **Objective:** {objective}\n\n"
        summary += f"📊 **Execution Strategy:** {strategy.capitalize()}\n\n"
        summary += f"**Tasks ({len(tasks)}):**\n"
        
        for i, task in enumerate(tasks, 1):
            task_id = task.get('task_id', f'task_{i}')
            desc = task.get('description', '')
            agents = task.get('agents', [])
            deps = task.get('dependencies', [])
            
            summary += f"\n{i}. **{task_id}:** {desc}\n"
            
            # Show assigned agents
            if agents and agents[0]:
                agent_names = [a.get('name', 'Unknown') for a in agents if a]
                summary += f"   👤 Agent(s): {', '.join(agent_names)}\n"
            else:
                summary += f"   ⚠️ No agent assigned\n"
            
            # Show dependencies
            if deps:
                summary += f"   🔗 Depends on: {', '.join(deps)}\n"
        
        summary += f"\n✅ Plan ready for execution by Orchestrator"
        
        return summary
    
    def clear_session(self, session_id: str):
        """Clear conversation history for a session"""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
            abi_logging(f"[🗑️] Cleared session {session_id}")
