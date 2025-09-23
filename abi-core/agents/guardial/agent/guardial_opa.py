import logging
import os
import json
from typing import Dict, Any, Optional
from collections.abc import AsyncIterable

from a2a.types import (
    SendStreamingMessageSuccessResponse,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent
)
from common import prompts
from agent.agent import AbiAgent
from agent.models.agent_models import GuardialResponse
from agent.policy_engine import get_policy_engine, PolicyDecision

from langchain_core.messages import AIMessage
from langchain_community.chat_models import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv('MODEL_NAME', 'tinyllama:latest')
memory = MemorySaver()

class AbiGuardialOPA(AbiAgent):
    """Guardian Agent with OPA Policy Engine Integration"""
    
    def __init__(self):
        super().__init__(
            agent_name='Abi Guardian Agent',
            description='Policy enforcement and compliance validation using OPA',
            content_types=['text', 'text/plain', 'application/json']
        )

        self.policy_engine = get_policy_engine()
        self.llm = ChatOllama(model_name=MODEL_NAME, temperature=0.0)
        logger.info(f'[🚀] Starting ABI Guardian Agent with OPA')
        
        self.abi_guardial = create_react_agent(
            self.llm,
            checkpointer=memory,
            prompt=prompts.GUARDIAL_COT_INSTRUCTIONS,
            response_format=GuardialResponse
        )

    async def validate_action(
        self,
        action: str,
        resource_type: str,
        source_agent: str,
        target_agent: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PolicyDecision:
        """
        Validate an action against ABI policies
        
        Args:
            action: Action being performed
            resource_type: Type of resource
            source_agent: Agent requesting action
            target_agent: Target agent (optional)
            content: Content being processed (optional)
            metadata: Additional context (optional)
            
        Returns:
            PolicyDecision with allow/deny and details
        """
        logger.info(f"[🛡️] Validating action: {action} from {source_agent} on {resource_type}")
        
        decision = await self.policy_engine.evaluate_policy(
            action=action,
            resource_type=resource_type,
            source_agent=source_agent,
            target_agent=target_agent,
            content=content,
            metadata=metadata
        )
        
        if decision.deny or not decision.allow:
            logger.warning(f"[🚫] Action DENIED: {action} - Risk Score: {decision.risk_score}")
        else:
            logger.info(f"[✅] Action ALLOWED: {action} - Risk Score: {decision.risk_score}")
            
        return decision

    async def validate_agent_communication(
        self,
        source_agent: str,
        target_agent: str,
        message_content: str,
        message_type: str = "text"
    ) -> PolicyDecision:
        """Validate inter-agent communication"""
        
        return await self.validate_action(
            action="agent_communication",
            resource_type="message",
            source_agent=source_agent,
            target_agent=target_agent,
            content=message_content,
            metadata={"message_type": message_type}
        )

    async def validate_resource_access(
        self,
        action: str,
        resource_type: str,
        resource_path: str,
        agent_name: str
    ) -> PolicyDecision:
        """Validate resource access (read/write/delete)"""
        
        return await self.validate_action(
            action=action,
            resource_type=resource_type,
            source_agent=agent_name,
            metadata={"resource_path": resource_path}
        )

    async def validate_workflow_execution(
        self,
        workflow_data: Dict[str, Any],
        executing_agent: str
    ) -> PolicyDecision:
        """Validate workflow execution against policies"""
        
        # Extract workflow details
        workflow_actions = workflow_data.get("actions", [])
        workflow_resources = workflow_data.get("resources", [])
        
        # Check each action in the workflow
        high_risk_actions = []
        total_risk = 0.0
        
        for action_data in workflow_actions:
            decision = await self.validate_action(
                action=action_data.get("type", "unknown"),
                resource_type=action_data.get("resource_type", "unknown"),
                source_agent=executing_agent,
                content=json.dumps(action_data),
                metadata={"workflow_step": action_data.get("step", 0)}
            )
            
            total_risk += decision.risk_score
            if decision.risk_score > 0.7:
                high_risk_actions.append(action_data)
        
        # Overall workflow decision
        avg_risk = total_risk / len(workflow_actions) if workflow_actions else 0.0
        workflow_allowed = avg_risk < 0.6 and len(high_risk_actions) == 0
        
        return PolicyDecision(
            allow=workflow_allowed,
            deny=not workflow_allowed,
            risk_score=avg_risk,
            audit_log={
                "workflow_validation": True,
                "total_actions": len(workflow_actions),
                "high_risk_actions": len(high_risk_actions),
                "average_risk": avg_risk
            },
            remediation_suggestions=[
                f"Review {len(high_risk_actions)} high-risk actions",
                "Consider breaking workflow into smaller steps",
                "Request human approval for high-risk workflow"
            ] if not workflow_allowed else []
        )

    async def stream(
        self, 
        query: str, 
        session_id: str, 
        task_id: str,
        source_agent: Optional[str] = None
    ) -> AsyncIterable[dict[str, any]]:
        """Stream policy validation with LLM reasoning"""
        
        config = {'configurable': {'thread_id': session_id}}
        
        # Parse the query to extract validation request
        try:
            validation_request = json.loads(query)
            action = validation_request.get("action", "unknown")
            resource_type = validation_request.get("resource_type", "unknown")
            requesting_agent = validation_request.get("source_agent", source_agent or "unknown")
            
            # Perform policy validation
            decision = await self.validate_action(
                action=action,
                resource_type=resource_type,
                source_agent=requesting_agent,
                content=validation_request.get("content"),
                metadata=validation_request.get("metadata")
            )
            
            # Generate LLM explanation of the decision
            explanation_prompt = f"""
            Policy Decision Analysis:
            
            Action: {action}
            Resource: {resource_type}
            Agent: {requesting_agent}
            Decision: {'ALLOWED' if decision.allow else 'DENIED'}
            Risk Score: {decision.risk_score:.2f}
            
            Rules Evaluated: {', '.join(decision.rules_evaluated)}
            
            Provide a clear explanation of why this decision was made and what it means for the agent workflow.
            If denied, explain the remediation steps clearly.
            """
            
            input_msg = {'messages': [('user', explanation_prompt)]}
            
            # Stream LLM explanation
            for chunk in self.abi_guardial.stream(input_msg, config, stream_mode='values'):
                message = chunk['messages'][-1]
                if isinstance(message, AIMessage):
                    yield {
                        'response_type': 'text',
                        'is_task_complete': False,
                        'require_user_input': False,
                        'content': message.content,
                        'policy_decision': {
                            'allow': decision.allow,
                            'risk_score': decision.risk_score,
                            'remediation': decision.remediation_suggestions
                        }
                    }
            
            # Final response with structured decision
            yield {
                'response_type': 'data',
                'is_task_complete': True,
                'require_user_input': False,
                'content': {
                    'policy_decision': decision.dict(),
                    'validation_complete': True
                }
            }
            
        except json.JSONDecodeError:
            # Handle plain text queries
            input_msg = {'messages': [('user', query)]}
            
            for chunk in self.abi_guardial.stream(input_msg, config, stream_mode='values'):
                message = chunk['messages'][-1]
                if isinstance(message, AIMessage):
                    yield {
                        'response_type': 'text',
                        'is_task_complete': False,
                        'require_user_input': False,
                        'content': message.content
                    }
            
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': 'Policy validation requires structured JSON input with action, resource_type, and source_agent fields.'
            }

    async def health_check(self) -> Dict[str, Any]:
        """Check Guardian and OPA health"""
        
        opa_healthy = await self.policy_engine.health_check()
        
        return {
            'guardian_status': 'healthy',
            'opa_status': 'healthy' if opa_healthy else 'unhealthy',
            'policy_engine': 'operational' if opa_healthy else 'degraded',
            'timestamp': json.dumps({"timestamp": "now"})  # Placeholder for actual timestamp
        }

    async def close(self):
        """Cleanup resources"""
        await self.policy_engine.close()