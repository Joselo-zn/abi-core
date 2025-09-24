"""
MCP Tool Interface for Guardial Agent

This module implements the MCP tool interface for guardial.evaluate,
allowing the semantic layer to invoke policy evaluations.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from agent.models.agent_models import (
    GuardialInputV1, 
    GuardialEvaluationResponse,
    SemanticSignals,
    AuditReport,
    ComplianceTrace,
    RiskAssessment,
    PolicyViolation,
    SemanticViolation
)
from agent.policy_engine_secure import get_secure_policy_engine, PolicyDecision
from agent.audit_persistence import get_audit_persistence_manager
from agent.metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)

class GuardialMCPTool:
    """MCP Tool interface for guardial.evaluate"""
    
    def __init__(self):
        self.policy_engine = get_secure_policy_engine()
        self.semantic_processor = SemanticSignalsProcessor()
        self.audit_manager = get_audit_persistence_manager()
        self.metrics = get_metrics_collector()
        
    async def evaluate(self, guardial_input: GuardialInputV1) -> GuardialEvaluationResponse:
        """
        Main evaluation endpoint called by MCP
        
        Args:
            guardial_input: Normalized input from MCP with semantic signals
            
        Returns:
            GuardialEvaluationResponse with decision, scores, and audit trail
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"🛡️ MCP Evaluation started for task_id: {guardial_input.task_id}")
            
            # Validate input
            if not self._validate_input(guardial_input):
                return self._create_error_response(
                    "Invalid input provided",
                    guardial_input.task_id,
                    start_time
                )
            
            # Process semantic signals
            semantic_result = await self.semantic_processor.process_signals(
                guardial_input.semantic_signals
            )
            
            # Evaluate policies with semantic integration
            policy_decision = await self._evaluate_with_semantics(
                guardial_input,
                semantic_result
            )
            
            # Calculate composite deviation score
            deviation_score = self._calculate_deviation_score(
                policy_decision,
                semantic_result
            )
            
            # Generate audit report
            audit_report = self._generate_audit_report(
                guardial_input,
                policy_decision,
                semantic_result
            )
            
            # Generate compliance trace
            compliance_trace = self._generate_compliance_trace(
                guardial_input,
                policy_decision,
                start_time
            )
            
            # Determine final decision
            final_decision = self._determine_final_decision(
                policy_decision,
                deviation_score,
                semantic_result
            )
            
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Record metrics
            self.metrics.record_evaluation_latency(
                processing_time,
                {"task_id": guardial_input.task_id, "decision": final_decision}
            )
            self.metrics.record_decision(
                final_decision,
                deviation_score,
                {"task_id": guardial_input.task_id}
            )
            
            # Record violations if any
            if audit_report.policy_violations:
                for violation in audit_report.policy_violations:
                    self.metrics.record_policy_violation(
                        violation.violation_type if hasattr(violation, 'violation_type') else violation.policy_name,
                        violation.severity,
                        {"task_id": guardial_input.task_id}
                    )
            
            # Record semantic signals
            if guardial_input.semantic_signals.pii_detected:
                self.metrics.record_semantic_signal(
                    "pii_detected",
                    guardial_input.semantic_signals.confidence_score,
                    {"task_id": guardial_input.task_id}
                )
            
            if guardial_input.semantic_signals.secrets_found:
                for secret in guardial_input.semantic_signals.secrets_found:
                    self.metrics.record_semantic_signal(
                        "secret_detected",
                        guardial_input.semantic_signals.confidence_score,
                        {"task_id": guardial_input.task_id, "secret_type": secret}
                    )
            
            response = GuardialEvaluationResponse(
                decision=final_decision,
                deviation_score=deviation_score,
                audit_report=audit_report,
                compliance_trace=compliance_trace,
                uncertain=policy_decision.get('uncertain', False),
                processing_time_ms=processing_time,
                policy_version=self.policy_engine.policy_loader.core_generator.version
            )
            
            # Persist audit report
            task_context = {
                "task_id": guardial_input.task_id,
                "context_id": guardial_input.context_id,
                "user_id": guardial_input.user_id
            }
            
            persist_success = await self.audit_manager.persist_report(response, task_context)
            if not persist_success:
                logger.warning(f"⚠️ Failed to persist audit report: {response.report_id}")
            
            logger.info(f"✅ MCP Evaluation completed: {final_decision} (score: {deviation_score:.3f}) - Report: {response.report_id}")
            return response
            
        except Exception as e:
            logger.error(f"🚨 MCP Evaluation failed: {e}")
            return self._create_error_response(
                f"Evaluation failed: {str(e)}",
                guardial_input.task_id,
                start_time,
                uncertain=True
            )
    
    def _validate_input(self, guardial_input: GuardialInputV1) -> bool:
        """Validate MCP input"""
        if not guardial_input.task_id:
            logger.error("Missing task_id in guardial input")
            return False
        
        if not guardial_input.context_id:
            logger.error("Missing context_id in guardial input")
            return False
        
        if not guardial_input.user_id:
            logger.error("Missing user_id in guardial input")
            return False
        
        return True
    
    async def _evaluate_with_semantics(
        self,
        guardial_input: GuardialInputV1,
        semantic_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate policies considering semantic signals"""
        
        # Prepare policy input
        policy_input = {
            "action": guardial_input.agent_outputs.get("action", "unknown"),
            "resource_type": guardial_input.agent_outputs.get("resource_type", "unknown"),
            "source_agent": guardial_input.agent_outputs.get("source_agent", "unknown"),
            "target_agent": guardial_input.agent_outputs.get("target_agent"),
            "content": str(guardial_input.agent_outputs.get("content", "")),
            "metadata": {
                **guardial_input.metadata,
                "task_id": guardial_input.task_id,
                "context_id": guardial_input.context_id,
                "user_id": guardial_input.user_id,
                "semantic_signals": semantic_result
            }
        }
        
        try:
            # Evaluate using policy engine
            policy_decision = await self.policy_engine.evaluate_policy(**policy_input)
            
            return {
                "policy_decision": policy_decision,
                "semantic_result": semantic_result,
                "uncertain": False
            }
            
        except Exception as e:
            logger.error(f"Policy evaluation failed: {e}")
            return {
                "policy_decision": None,
                "semantic_result": semantic_result,
                "uncertain": True,
                "error": str(e)
            }
    
    def _calculate_deviation_score(
        self,
        policy_result: Dict[str, Any],
        semantic_result: Dict[str, Any]
    ) -> float:
        """Calculate composite deviation score"""
        
        # Base policy score
        policy_decision = policy_result.get("policy_decision")
        if policy_decision:
            policy_score = policy_decision.risk_score
        else:
            policy_score = 1.0  # Maximum risk if policy evaluation failed
        
        # Semantic risk score
        semantic_score = semantic_result.get("risk_score", 0.0)
        
        # Combine scores with weights
        policy_weight = 0.7
        semantic_weight = 0.3
        
        composite_score = (policy_score * policy_weight) + (semantic_score * semantic_weight)
        
        # Add uncertainty penalty
        if policy_result.get("uncertain", False):
            composite_score = min(1.0, composite_score + 0.2)
        
        return round(composite_score, 3)
    
    def _generate_audit_report(
        self,
        guardial_input: GuardialInputV1,
        policy_result: Dict[str, Any],
        semantic_result: Dict[str, Any]
    ) -> AuditReport:
        """Generate structured audit report"""
        
        policy_violations = []
        semantic_violations = []
        
        # Extract policy violations
        policy_decision = policy_result.get("policy_decision")
        if policy_decision and policy_decision.deny:
            for suggestion in policy_decision.remediation_suggestions:
                if "BLOCKED BY CORE SECURITY POLICY" in suggestion:
                    policy_violations.append(PolicyViolation(
                        policy_name="core_security",
                        rule_name="core_policy_violation",
                        severity="critical",
                        description=suggestion,
                        remediation="Contact system administrator"
                    ))
        
        # Extract semantic violations
        semantic_signals = guardial_input.semantic_signals
        if semantic_signals.pii_detected:
            semantic_violations.append(SemanticViolation(
                violation_type="pii_detection",
                severity="high",
                description="Personally Identifiable Information detected",
                confidence=semantic_signals.confidence_score,
                remediation="Remove or redact PII before processing"
            ))
        
        if semantic_signals.secrets_found:
            for secret in semantic_signals.secrets_found:
                semantic_violations.append(SemanticViolation(
                    violation_type="secret_exposure",
                    severity="critical",
                    description=f"Secret detected: {secret}",
                    confidence=semantic_signals.confidence_score,
                    remediation="Remove secrets and rotate credentials"
                ))
        
        # Create risk assessment
        risk_assessment = RiskAssessment(
            overall_risk=self._calculate_deviation_score(policy_result, semantic_result),
            policy_risk=policy_decision.risk_score if policy_decision else 1.0,
            semantic_risk=semantic_result.get("risk_score", 0.0),
            risk_factors=self._extract_risk_factors(policy_result, semantic_result),
            mitigation_suggestions=self._generate_mitigation_suggestions(policy_result, semantic_result)
        )
        
        return AuditReport(
            policy_violations=policy_violations,
            semantic_violations=semantic_violations,
            risk_assessment=risk_assessment,
            remediation_suggestions=self._generate_remediation_suggestions(policy_result, semantic_result)
        )
    
    def _generate_compliance_trace(
        self,
        guardial_input: GuardialInputV1,
        policy_result: Dict[str, Any],
        start_time: datetime
    ) -> ComplianceTrace:
        """Generate compliance trace for audit trail"""
        
        rules_evaluated = []
        decision_path = []
        timestamps = {
            "evaluation_started": start_time,
            "policy_evaluation": datetime.utcnow()
        }
        
        policy_decision = policy_result.get("policy_decision")
        if policy_decision:
            rules_evaluated.extend(policy_decision.rules_evaluated)
            
            if policy_decision.allow:
                decision_path.append("policy_allow")
            if policy_decision.deny:
                decision_path.append("policy_deny")
        
        # Add semantic evaluation path
        if guardial_input.semantic_signals.pii_detected:
            decision_path.append("semantic_pii_detected")
        
        if guardial_input.semantic_signals.secrets_found:
            decision_path.append("semantic_secrets_found")
        
        timestamps["evaluation_completed"] = datetime.utcnow()
        
        return ComplianceTrace(
            rules_evaluated=rules_evaluated,
            decision_path=decision_path,
            timestamps=timestamps,
            evaluation_context={
                "task_id": guardial_input.task_id,
                "context_id": guardial_input.context_id,
                "user_id": guardial_input.user_id,
                "policy_refs": guardial_input.policy_refs
            }
        )
    
    def _determine_final_decision(
        self,
        policy_result: Dict[str, Any],
        deviation_score: float,
        semantic_result: Dict[str, Any]
    ) -> str:
        """Determine final decision based on all factors"""
        
        policy_decision = policy_result.get("policy_decision")
        
        # Hard deny from core policies
        if policy_decision and policy_decision.deny:
            return "deny"
        
        # High deviation score requires review
        if deviation_score > 0.8:
            return "review"
        
        # Medium deviation score with semantic violations
        if deviation_score > 0.5 and semantic_result.get("violations_found", False):
            return "review"
        
        # Allow if policy allows and low risk
        if policy_decision and policy_decision.allow and deviation_score < 0.3:
            return "allow"
        
        # Default to review for uncertain cases
        return "review"
    
    def _extract_risk_factors(
        self,
        policy_result: Dict[str, Any],
        semantic_result: Dict[str, Any]
    ) -> List[str]:
        """Extract risk factors from evaluation results"""
        factors = []
        
        policy_decision = policy_result.get("policy_decision")
        if policy_decision and policy_decision.deny:
            factors.append("Core policy violation")
        
        if semantic_result.get("pii_detected", False):
            factors.append("PII detected")
        
        if semantic_result.get("secrets_found", []):
            factors.append("Secrets exposed")
        
        if semantic_result.get("scope_creep", 0) > 0.5:
            factors.append("Scope creep detected")
        
        return factors
    
    def _generate_mitigation_suggestions(
        self,
        policy_result: Dict[str, Any],
        semantic_result: Dict[str, Any]
    ) -> List[str]:
        """Generate mitigation suggestions"""
        suggestions = []
        
        policy_decision = policy_result.get("policy_decision")
        if policy_decision:
            suggestions.extend(policy_decision.remediation_suggestions)
        
        if semantic_result.get("pii_detected", False):
            suggestions.append("Implement PII redaction before processing")
        
        if semantic_result.get("secrets_found", []):
            suggestions.append("Remove secrets and implement secure credential management")
        
        return suggestions
    
    def _generate_remediation_suggestions(
        self,
        policy_result: Dict[str, Any],
        semantic_result: Dict[str, Any]
    ) -> List[str]:
        """Generate remediation suggestions"""
        return self._generate_mitigation_suggestions(policy_result, semantic_result)
    
    def _create_error_response(
        self,
        error_message: str,
        task_id: str,
        start_time: datetime,
        uncertain: bool = True
    ) -> GuardialEvaluationResponse:
        """Create error response for failed evaluations"""
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return GuardialEvaluationResponse(
            decision="review",
            deviation_score=1.0,
            audit_report=AuditReport(
                risk_assessment=RiskAssessment(
                    overall_risk=1.0,
                    policy_risk=1.0,
                    semantic_risk=0.0,
                    risk_factors=["Evaluation failed"],
                    mitigation_suggestions=["Manual review required", "Check system logs"]
                ),
                remediation_suggestions=["Manual review required due to evaluation failure"]
            ),
            compliance_trace=ComplianceTrace(
                rules_evaluated=["error_handling"],
                decision_path=["evaluation_failed"],
                timestamps={"evaluation_started": start_time, "evaluation_failed": datetime.utcnow()},
                evaluation_context={"task_id": task_id, "error": error_message}
            ),
            uncertain=uncertain,
            processing_time_ms=processing_time
        )


class SemanticSignalsProcessor:
    """Process semantic signals from vector store analysis"""
    
    async def process_signals(self, signals: SemanticSignals) -> Dict[str, Any]:
        """Process semantic signals and return analysis results"""
        
        try:
            # Calculate semantic risk score
            risk_score = self._calculate_semantic_risk(signals)
            
            # Detect violations
            violations_found = (
                signals.pii_detected or 
                len(signals.secrets_found) > 0 or
                signals.scope_creep > 0.5
            )
            
            return {
                "risk_score": risk_score,
                "violations_found": violations_found,
                "pii_detected": signals.pii_detected,
                "secrets_found": signals.secrets_found,
                "scope_creep": signals.scope_creep,
                "bias_indicators": signals.bias_indicators,
                "confidence": signals.confidence_score
            }
            
        except Exception as e:
            logger.error(f"Semantic signals processing failed: {e}")
            return {
                "risk_score": 0.5,  # Medium risk for processing failure
                "violations_found": False,
                "error": str(e)
            }
    
    def _calculate_semantic_risk(self, signals: SemanticSignals) -> float:
        """Calculate risk score from semantic signals"""
        
        risk_score = 0.0
        
        # PII detection adds significant risk
        if signals.pii_detected:
            risk_score += 0.4
        
        # Secrets are critical
        if signals.secrets_found:
            risk_score += 0.6
        
        # Scope creep adds proportional risk
        risk_score += signals.scope_creep * 0.3
        
        # Bias indicators add moderate risk
        if signals.bias_indicators:
            risk_score += len(signals.bias_indicators) * 0.1
        
        # Risk level mapping
        risk_level_scores = {
            "low": 0.0,
            "medium": 0.2,
            "high": 0.4,
            "critical": 0.6
        }
        risk_score += risk_level_scores.get(signals.risk_level, 0.0)
        
        # Apply confidence factor
        risk_score *= signals.confidence_score
        
        return min(1.0, risk_score)


# Singleton instance
_guardial_mcp_tool = None

def get_guardial_mcp_tool() -> GuardialMCPTool:
    """Get singleton MCP tool instance"""
    global _guardial_mcp_tool
    if _guardial_mcp_tool is None:
        _guardial_mcp_tool = GuardialMCPTool()
    return _guardial_mcp_tool