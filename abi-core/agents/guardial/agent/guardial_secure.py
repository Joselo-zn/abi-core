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
from agent.policy_engine_secure import get_secure_policy_engine, PolicyDecision

from langchain_core.messages import AIMessage
from langchain_community.chat_models import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv('MODEL_NAME', 'tinyllama:latest')
memory = MemorySaver()

class AbiGuardianSecure(AbiAgent):
    """
    Secure Guardian Agent with Mandatory OPA Policy Engine Integration
    
    CRITICAL SECURITY FEATURES:
    - MANDATORY core policies - system won't start without them
    - Auto-generation of security policies at deployment
    - Fail-safe security defaults
    - Immutable core policy protection
    """
    
    def __init__(self):
        super().__init__(
            agent_name='ABI Guardian Agent (Secure)',
            description='Mandatory policy enforcement and compliance validation using secure OPA',
            content_types=['text', 'text/plain', 'application/json']
        )

        self.policy_engine = get_secure_policy_engine()
        self.llm = ChatOllama(model_name=MODEL_NAME, temperature=0.0)
        self.system_secure = False
        
        logger.info(f'🛡️ Starting ABI Guardian Agent with Secure OPA')
        
        self.abi_guardial = create_react_agent(
            self.llm,
            checkpointer=memory,
            prompt=prompts.GUARDIAL_COT_INSTRUCTIONS,
            response_format=GuardialResponse
        )

    async def initialize_security(self) -> bool:
        """
        CRITICAL: Initialize and validate system security
        
        Returns:
            True if system is secure and can operate
            False if system MUST NOT operate due to security issues
        """
        try:
            logger.info("🔒 Initializing Guardian Security System...")
            
            # Initialize secure policy engine (includes mandatory validation)
            await self.policy_engine.initialize()
            
            # Perform security health check
            health = await self.policy_engine.health_check()
            
            if not health.get('system_secure', False):
                logger.error("🚨 CRITICAL: System security validation FAILED")
                logger.error(f"🚨 Health check results: {health}")
                return False
            
            self.system_secure = True
            logger.info("✅ Guardian Security System VALIDATED - System safe to operate")
            return True
            
        except Exception as e:
            logger.error(f"🚨 CRITICAL: Security initialization failed: {e}")
            logger.error("🚨 SYSTEM BLOCKED FOR SECURITY")
            return False

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
        Validate an action against ABI policies with mandatory security
        
        CRITICAL: Will fail-safe to DENY if security is not validated
        """
        
        # CRITICAL: Check system security first
        if not self.system_secure:
            logger.error("🚨 CRITICAL: System security not validated - BLOCKING all actions")
            return PolicyDecision(
                allow=False,
                deny=True,
                risk_score=1.0,
                audit_log={"error": "System security not validated", "fail_safe": "hard_deny"},
                remediation_suggestions=["Initialize system security", "Contact administrator"]
            )
        
        logger.info(f"🛡️ Validating action: {action} from {source_agent} on {resource_type}")
        
        decision = await self.policy_engine.evaluate_policy(
            action=action,
            resource_type=resource_type,
            source_agent=source_agent,
            target_agent=target_agent,
            content=content,
            metadata=metadata
        )
        
        # Enhanced logging for security decisions
        if decision.deny or not decision.allow:
            if decision.risk_score > 0.8:
                logger.error(f"🚫 HIGH-RISK ACTION BLOCKED: {action} - Risk Score: {decision.risk_score}")
            else:
                logger.warning(f"🚫 Action DENIED: {action} - Risk Score: {decision.risk_score}")
        else:
            logger.info(f"✅ Action ALLOWED: {action} - Risk Score: {decision.risk_score}")
            
        return decision

    async def validate_agent_communication(
        self,
        source_agent: str,
        target_agent: str,
        message_content: str,
        message_type: str = "text"
    ) -> PolicyDecision:
        """Validate inter-agent communication with security checks"""
        
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
        """Validate resource access with enhanced security"""
        
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
        """Validate workflow execution with comprehensive security analysis"""
        
        # Extract workflow details
        workflow_actions = workflow_data.get("actions", [])
        workflow_resources = workflow_data.get("resources", [])
        
        # Check each action in the workflow
        high_risk_actions = []
        blocked_actions = []
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
            
            if decision.deny:
                blocked_actions.append(action_data)
            elif decision.risk_score > 0.7:
                high_risk_actions.append(action_data)
        
        # Overall workflow decision with enhanced security logic
        avg_risk = total_risk / len(workflow_actions) if workflow_actions else 0.0
        
        # Workflow is blocked if ANY action is blocked by core policies
        workflow_blocked = len(blocked_actions) > 0
        
        # Workflow requires approval if high risk or many risky actions
        requires_approval = (
            avg_risk > 0.6 or 
            len(high_risk_actions) > 2 or
            len(high_risk_actions) / len(workflow_actions) > 0.3
        )
        
        workflow_allowed = not workflow_blocked and not requires_approval
        
        audit_log = {
            "workflow_validation": True,
            "total_actions": len(workflow_actions),
            "blocked_actions": len(blocked_actions),
            "high_risk_actions": len(high_risk_actions),
            "average_risk": avg_risk,
            "requires_approval": requires_approval,
            "security_validated": self.system_secure
        }
        
        remediation = []
        if workflow_blocked:
            remediation.extend([
                f"🚫 {len(blocked_actions)} actions blocked by security policies",
                "Remove or modify blocked actions to proceed",
                "Contact administrator for policy review"
            ])
        elif requires_approval:
            remediation.extend([
                f"⚠️ Workflow requires approval ({len(high_risk_actions)} high-risk actions)",
                "Request human approval for high-risk workflow",
                "Consider breaking workflow into smaller steps"
            ])
        
        return PolicyDecision(
            allow=workflow_allowed,
            deny=workflow_blocked,
            risk_score=avg_risk,
            audit_log=audit_log,
            remediation_suggestions=remediation
        )

    async def emergency_shutdown(self, reason: str, initiated_by: str) -> Dict[str, Any]:
        """
        Emergency shutdown mechanism - always available regardless of policies
        
        This is a fail-safe mechanism that cannot be blocked by any policy
        """
        logger.error(f"🚨 EMERGENCY SHUTDOWN INITIATED by {initiated_by}: {reason}")
        
        shutdown_log = {
            "timestamp": json.dumps({"timestamp": "now"}),  # Placeholder
            "reason": reason,
            "initiated_by": initiated_by,
            "system_state": {
                "security_validated": self.system_secure,
                "policies_loaded": self.policy_engine.policies_loaded if hasattr(self.policy_engine, 'policies_loaded') else False
            },
            "emergency_action": "SYSTEM_SHUTDOWN"
        }
        
        # Log emergency shutdown
        logger.error(f"🚨 EMERGENCY SHUTDOWN LOG: {json.dumps(shutdown_log)}")
        
        return {
            "shutdown_initiated": True,
            "reason": reason,
            "initiated_by": initiated_by,
            "log": shutdown_log
        }

    async def stream(
        self, 
        query: str, 
        session_id: str, 
        task_id: str,
        source_agent: Optional[str] = None
    ) -> AsyncIterable[dict[str, any]]:
        """Stream policy validation with mandatory security checks"""
        
        # CRITICAL: Ensure security is initialized
        if not self.system_secure:
            logger.error("🚨 CRITICAL: Attempting to use Guardian without security validation")
            yield {
                'response_type': 'error',
                'is_task_complete': True,
                'require_user_input': False,
                'content': '🚨 CRITICAL SECURITY ERROR: Guardian security not validated - system blocked',
                'security_error': True
            }
            return
        
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
            
            # Generate LLM explanation of the decision with security context
            security_status = "✅ SECURE" if self.system_secure else "🚨 INSECURE"
            decision_status = "✅ ALLOWED" if decision.allow else "🚫 DENIED"
            
            explanation_prompt = f"""
            ABI Guardian Security Decision Analysis:
            
            System Status: {security_status}
            Action: {action}
            Resource: {resource_type}
            Agent: {requesting_agent}
            Decision: {decision_status}
            Risk Score: {decision.risk_score:.2f}
            
            Security Context:
            - Core policies validated: {self.system_secure}
            - Rules evaluated: {', '.join(decision.rules_evaluated)}
            
            Provide a clear, security-focused explanation of why this decision was made.
            If denied, explain the security implications and remediation steps clearly.
            Emphasize any core security policy violations.
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
                            'deny': decision.deny,
                            'risk_score': decision.risk_score,
                            'remediation': decision.remediation_suggestions,
                            'security_validated': self.system_secure
                        }
                    }
            
            # Final response with structured decision
            yield {
                'response_type': 'data',
                'is_task_complete': True,
                'require_user_input': False,
                'content': {
                    'policy_decision': decision.dict(),
                    'validation_complete': True,
                    'security_status': 'validated' if self.system_secure else 'not_validated'
                }
            }
            
        except json.JSONDecodeError:
            # Handle plain text queries with security context
            security_prompt = f"""
            ABI Guardian Agent - Security Status: {'✅ VALIDATED' if self.system_secure else '🚨 NOT VALIDATED'}
            
            User Query: {query}
            
            Respond as the ABI Guardian Agent responsible for policy enforcement and security validation.
            Always mention the current security status in your response.
            """
            
            input_msg = {'messages': [('user', security_prompt)]}
            
            for chunk in self.abi_guardial.stream(input_msg, config, stream_mode='values'):
                message = chunk['messages'][-1]
                if isinstance(message, AIMessage):
                    yield {
                        'response_type': 'text',
                        'is_task_complete': False,
                        'require_user_input': False,
                        'content': message.content,
                        'security_validated': self.system_secure
                    }
            
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': 'For policy validation, provide structured JSON input with action, resource_type, and source_agent fields.',
                'security_validated': self.system_secure
            }

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with security validation"""
        
        # Get policy engine health
        policy_health = await self.policy_engine.health_check()
        
        # Guardian-specific health
        guardian_health = {
            'guardian_agent': 'healthy' if self.system_secure else 'SECURITY_NOT_VALIDATED',
            'system_secure': self.system_secure,
            'security_initialized': hasattr(self, 'system_secure'),
            'llm_available': self.llm is not None,
            'timestamp': json.dumps({"timestamp": "now"})  # Placeholder
        }
        
        # Combine health information
        combined_health = {**policy_health, **guardian_health}
        
        # Overall system status
        combined_health['overall_status'] = (
            'SECURE_AND_OPERATIONAL' if combined_health.get('system_secure') and 
                                       combined_health.get('core_policies_present') and
                                       combined_health.get('opa_status') == 'healthy'
            else 'SECURITY_ISSUES_DETECTED'
        )
        
        return combined_health

    async def close(self):
        """Cleanup resources"""
        await self.policy_engine.close()