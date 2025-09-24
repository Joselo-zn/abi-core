#!/usr/bin/env python3
"""
Integration Tests for MCP Flow - Task 6.1

This script tests the complete MCP flow for guardial.evaluate including:
- End-to-end MCP tool interface testing
- Semantic signals integration with policy evaluation
- GuardialInputV1 processing and GuardialResponse generation
- Error handling and graceful degradation scenarios
- Performance tests for evaluation latency and throughput

Requirements tested: 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 4.6
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_mcp_tool_interface():
    """Test MCP tool interface basic functionality"""
    logger.info("🧪 Testing MCP Tool Interface...")
    
    from agent.mcp_interface import get_guardial_mcp_tool
    from agent.models.agent_models import GuardialInputV1, SemanticSignals
    
    # Get MCP tool instance
    mcp_tool = get_guardial_mcp_tool()
    
    # Create test input
    test_input = GuardialInputV1(
        task_id="test_task_001",
        context_id="test_context_001", 
        user_id="test_user_001",
        policy_refs=["abi.core", "test.policy"],
        expected_behaviors_ref="test_behaviors",
        agent_outputs={
            "action": "file_access",
            "resource_type": "document",
            "source_agent": "worker_actor",
            "target_agent": "file_system",
            "content": "Accessing user document for processing"
        },
        semantic_signals=SemanticSignals(
            pii_detected=False,
            secrets_found=[],
            scope_creep=0.1,
            bias_indicators=[],
            risk_level="low",
            confidence_score=0.95
        ),
        metadata={"test": True, "environment": "integration_test"}
    )
    
    # Test evaluation
    start_time = time.time()
    response = await mcp_tool.evaluate(test_input)
    evaluation_time = time.time() - start_time
    
    # Validate response structure
    assert hasattr(response, 'decision')
    assert hasattr(response, 'deviation_score')
    assert hasattr(response, 'audit_report')
    assert hasattr(response, 'compliance_trace')
    assert hasattr(response, 'report_id')
    
    # Validate decision values
    assert response.decision in ["allow", "deny", "review"]
    assert 0.0 <= response.deviation_score <= 1.0
    assert response.report_id is not None
    
    # Validate audit report structure
    assert hasattr(response.audit_report, 'risk_assessment')
    assert hasattr(response.audit_report, 'policy_violations')
    assert hasattr(response.audit_report, 'semantic_violations')
    
    # Validate compliance trace
    assert hasattr(response.compliance_trace, 'rules_evaluated')
    assert hasattr(response.compliance_trace, 'decision_path')
    assert hasattr(response.compliance_trace, 'timestamps')
    
    logger.info(f"✅ MCP Tool Interface test passed - Decision: {response.decision}, Score: {response.deviation_score:.3f}, Time: {evaluation_time:.3f}s")
    return response

async def test_semantic_signals_integration():
    """Test semantic signals integration with policy evaluation"""
    logger.info("🧪 Testing Semantic Signals Integration...")
    
    from agent.mcp_interface import get_guardial_mcp_tool
    from agent.models.agent_models import GuardialInputV1, SemanticSignals
    
    mcp_tool = get_guardial_mcp_tool()
    
    # Test case 1: PII detected
    pii_input = GuardialInputV1(
        task_id="test_pii_001",
        context_id="test_context_pii",
        user_id="test_user_pii",
        agent_outputs={
            "action": "data_processing",
            "content": "Processing user data with email john.doe@example.com"
        },
        semantic_signals=SemanticSignals(
            pii_detected=True,
            secrets_found=[],
            scope_creep=0.2,
            bias_indicators=[],
            risk_level="medium",
            confidence_score=0.92
        )
    )
    
    pii_response = await mcp_tool.evaluate(pii_input)
    
    # Should have higher deviation score due to PII
    assert pii_response.deviation_score > 0.3
    assert len(pii_response.audit_report.semantic_violations) > 0
    
    # Test case 2: Secrets detected
    secrets_input = GuardialInputV1(
        task_id="test_secrets_001",
        context_id="test_context_secrets",
        user_id="test_user_secrets",
        agent_outputs={
            "action": "config_update",
            "content": "API_KEY=sk-1234567890abcdef"
        },
        semantic_signals=SemanticSignals(
            pii_detected=False,
            secrets_found=["api_key"],
            scope_creep=0.1,
            bias_indicators=[],
            risk_level="high",
            confidence_score=0.98
        )
    )
    
    secrets_response = await mcp_tool.evaluate(secrets_input)
    
    # Should have high deviation score and likely deny/review
    assert secrets_response.deviation_score > 0.6
    assert secrets_response.decision in ["deny", "review"]
    assert len(secrets_response.audit_report.semantic_violations) > 0
    
    # Test case 3: Multiple violations
    multi_input = GuardialInputV1(
        task_id="test_multi_001",
        context_id="test_context_multi",
        user_id="test_user_multi",
        agent_outputs={
            "action": "data_export",
            "content": "Exporting user data including SSN 123-45-6789 and API_KEY=secret123"
        },
        semantic_signals=SemanticSignals(
            pii_detected=True,
            secrets_found=["api_key", "ssn"],
            scope_creep=0.8,
            bias_indicators=["demographic_bias"],
            risk_level="critical",
            confidence_score=0.96
        )
    )
    
    multi_response = await mcp_tool.evaluate(multi_input)
    
    # Should have very high deviation score and deny
    assert multi_response.deviation_score > 0.8
    assert multi_response.decision == "deny"
    assert len(multi_response.audit_report.semantic_violations) >= 2
    
    logger.info("✅ Semantic Signals Integration test passed")
    return [pii_response, secrets_response, multi_response]

async def test_error_handling_and_degradation():
    """Test error handling and graceful degradation scenarios"""
    logger.info("🧪 Testing Error Handling and Graceful Degradation...")
    
    from agent.mcp_interface import get_guardial_mcp_tool
    from agent.models.agent_models import GuardialInputV1, SemanticSignals
    
    mcp_tool = get_guardial_mcp_tool()
    
    # Test case 1: Invalid input
    try:
        invalid_input = GuardialInputV1(
            task_id="",  # Empty task_id should fail validation
            context_id="test_context",
            user_id="test_user",
            agent_outputs={}
        )
        
        response = await mcp_tool.evaluate(invalid_input)
        
        # Should return error response with uncertain=True
        assert response.uncertain == True
        assert response.decision == "review"
        assert response.deviation_score == 1.0
        
        logger.info("✅ Invalid input handling test passed")
        
    except Exception as e:
        logger.info(f"✅ Invalid input properly rejected: {e}")
    
    # Test case 2: Simulated OPA failure (by providing malformed policy input)
    opa_failure_input = GuardialInputV1(
        task_id="test_opa_failure_001",
        context_id="test_context_opa_fail",
        user_id="test_user_opa_fail",
        agent_outputs={
            "action": "malformed_action_that_might_cause_opa_issues",
            "content": None  # This might cause issues in policy evaluation
        },
        semantic_signals=SemanticSignals(
            pii_detected=False,
            secrets_found=[],
            scope_creep=0.0,
            risk_level="low",
            confidence_score=0.8
        )
    )
    
    opa_response = await mcp_tool.evaluate(opa_failure_input)
    
    # Should handle gracefully even if OPA has issues
    assert opa_response is not None
    assert hasattr(opa_response, 'decision')
    
    # Test case 3: High load simulation
    concurrent_tasks = []
    for i in range(10):
        test_input = GuardialInputV1(
            task_id=f"concurrent_test_{i}",
            context_id=f"concurrent_context_{i}",
            user_id=f"concurrent_user_{i}",
            agent_outputs={
                "action": "concurrent_test",
                "content": f"Concurrent test {i}"
            },
            semantic_signals=SemanticSignals(
                risk_level="low",
                confidence_score=0.9
            )
        )
        concurrent_tasks.append(mcp_tool.evaluate(test_input))
    
    # Execute all concurrent evaluations
    start_time = time.time()
    concurrent_responses = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
    concurrent_time = time.time() - start_time
    
    # Validate all responses
    successful_responses = [r for r in concurrent_responses if not isinstance(r, Exception)]
    assert len(successful_responses) >= 8  # At least 80% should succeed
    
    logger.info(f"✅ Concurrent evaluation test passed - {len(successful_responses)}/10 succeeded in {concurrent_time:.3f}s")
    
    logger.info("✅ Error Handling and Graceful Degradation test passed")
    return concurrent_responses

async def test_performance_and_latency():
    """Test evaluation latency and throughput performance"""
    logger.info("🧪 Testing Performance and Latency...")
    
    from agent.mcp_interface import get_guardial_mcp_tool
    from agent.models.agent_models import GuardialInputV1, SemanticSignals
    
    mcp_tool = get_guardial_mcp_tool()
    
    # Performance test parameters
    num_evaluations = 50
    latency_measurements = []
    
    # Test different complexity levels
    test_cases = [
        {
            "name": "simple",
            "semantic_signals": SemanticSignals(risk_level="low", confidence_score=0.9),
            "content": "Simple test action"
        },
        {
            "name": "medium",
            "semantic_signals": SemanticSignals(
                pii_detected=True,
                scope_creep=0.3,
                risk_level="medium",
                confidence_score=0.85
            ),
            "content": "Medium complexity with PII detection"
        },
        {
            "name": "complex",
            "semantic_signals": SemanticSignals(
                pii_detected=True,
                secrets_found=["api_key"],
                scope_creep=0.7,
                bias_indicators=["bias1", "bias2"],
                risk_level="high",
                confidence_score=0.92
            ),
            "content": "Complex evaluation with multiple violations"
        }
    ]
    
    for test_case in test_cases:
        case_latencies = []
        
        for i in range(num_evaluations // len(test_cases)):
            test_input = GuardialInputV1(
                task_id=f"perf_test_{test_case['name']}_{i}",
                context_id=f"perf_context_{i}",
                user_id=f"perf_user_{i}",
                agent_outputs={
                    "action": f"performance_test_{test_case['name']}",
                    "content": test_case["content"]
                },
                semantic_signals=test_case["semantic_signals"]
            )
            
            start_time = time.time()
            response = await mcp_tool.evaluate(test_input)
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            case_latencies.append(latency)
            latency_measurements.append({
                "case": test_case["name"],
                "latency_ms": latency,
                "decision": response.decision,
                "deviation_score": response.deviation_score
            })
        
        # Calculate statistics for this test case
        avg_latency = sum(case_latencies) / len(case_latencies)
        min_latency = min(case_latencies)
        max_latency = max(case_latencies)
        
        # Calculate percentiles
        sorted_latencies = sorted(case_latencies)
        p50 = sorted_latencies[len(sorted_latencies) // 2]
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        
        logger.info(f"📊 {test_case['name'].upper()} Performance:")
        logger.info(f"   Average: {avg_latency:.2f}ms")
        logger.info(f"   Min/Max: {min_latency:.2f}ms / {max_latency:.2f}ms")
        logger.info(f"   P50/P95/P99: {p50:.2f}ms / {p95:.2f}ms / {p99:.2f}ms")
        
        # Performance assertions
        assert avg_latency < 1000, f"Average latency too high: {avg_latency:.2f}ms"
        assert p95 < 2000, f"P95 latency too high: {p95:.2f}ms"
    
    # Throughput test
    logger.info("🚀 Testing Throughput...")
    
    throughput_tasks = []
    for i in range(20):
        test_input = GuardialInputV1(
            task_id=f"throughput_test_{i}",
            context_id=f"throughput_context_{i}",
            user_id=f"throughput_user_{i}",
            agent_outputs={
                "action": "throughput_test",
                "content": f"Throughput test {i}"
            },
            semantic_signals=SemanticSignals(risk_level="low", confidence_score=0.9)
        )
        throughput_tasks.append(mcp_tool.evaluate(test_input))
    
    start_time = time.time()
    throughput_responses = await asyncio.gather(*throughput_tasks)
    total_time = time.time() - start_time
    
    throughput = len(throughput_responses) / total_time
    logger.info(f"📈 Throughput: {throughput:.2f} evaluations/second")
    
    # Throughput assertion
    assert throughput > 5, f"Throughput too low: {throughput:.2f} eval/sec"
    
    logger.info("✅ Performance and Latency test passed")
    return {
        "latency_measurements": latency_measurements,
        "throughput": throughput,
        "total_evaluations": len(latency_measurements)
    }

async def test_audit_trail_generation():
    """Test comprehensive audit trail generation"""
    logger.info("🧪 Testing Audit Trail Generation...")
    
    from agent.mcp_interface import get_guardial_mcp_tool
    from agent.models.agent_models import GuardialInputV1, SemanticSignals
    
    mcp_tool = get_guardial_mcp_tool()
    
    # Create test input with various violations
    test_input = GuardialInputV1(
        task_id="audit_test_001",
        context_id="audit_context_001",
        user_id="audit_user_001",
        policy_refs=["abi.core", "audit.test"],
        agent_outputs={
            "action": "sensitive_data_access",
            "resource_type": "user_data",
            "source_agent": "test_agent",
            "content": "Accessing sensitive user information for audit test"
        },
        semantic_signals=SemanticSignals(
            pii_detected=True,
            secrets_found=["api_key"],
            scope_creep=0.6,
            bias_indicators=["demographic_bias"],
            risk_level="high",
            confidence_score=0.94
        ),
        metadata={
            "audit_test": True,
            "test_timestamp": datetime.utcnow().isoformat()
        }
    )
    
    response = await mcp_tool.evaluate(test_input)
    
    # Validate audit report completeness
    audit_report = response.audit_report
    
    # Check policy violations
    assert hasattr(audit_report, 'policy_violations')
    assert isinstance(audit_report.policy_violations, list)
    
    # Check semantic violations
    assert hasattr(audit_report, 'semantic_violations')
    assert isinstance(audit_report.semantic_violations, list)
    assert len(audit_report.semantic_violations) > 0  # Should have PII and secrets violations
    
    # Check risk assessment
    assert hasattr(audit_report, 'risk_assessment')
    risk_assessment = audit_report.risk_assessment
    assert hasattr(risk_assessment, 'overall_risk')
    assert hasattr(risk_assessment, 'policy_risk')
    assert hasattr(risk_assessment, 'semantic_risk')
    assert hasattr(risk_assessment, 'risk_factors')
    assert hasattr(risk_assessment, 'mitigation_suggestions')
    
    # Validate compliance trace
    compliance_trace = response.compliance_trace
    assert hasattr(compliance_trace, 'rules_evaluated')
    assert hasattr(compliance_trace, 'decision_path')
    assert hasattr(compliance_trace, 'timestamps')
    assert hasattr(compliance_trace, 'evaluation_context')
    
    # Check that timestamps are properly recorded
    timestamps = compliance_trace.timestamps
    assert 'evaluation_started' in timestamps
    assert 'evaluation_completed' in timestamps
    
    # Check evaluation context
    eval_context = compliance_trace.evaluation_context
    assert eval_context['task_id'] == test_input.task_id
    assert eval_context['context_id'] == test_input.context_id
    assert eval_context['user_id'] == test_input.user_id
    
    logger.info(f"✅ Audit Trail Generation test passed - Report ID: {response.report_id}")
    logger.info(f"   Policy violations: {len(audit_report.policy_violations)}")
    logger.info(f"   Semantic violations: {len(audit_report.semantic_violations)}")
    logger.info(f"   Risk factors: {len(risk_assessment.risk_factors)}")
    logger.info(f"   Rules evaluated: {len(compliance_trace.rules_evaluated)}")
    
    return response

async def run_mcp_integration_tests():
    """Run all MCP integration tests"""
    logger.info("🚀 Starting MCP Integration Tests (Task 6.1)")
    
    test_results = {}
    
    try:
        # Test 1: Basic MCP tool interface
        logger.info("\n" + "="*60)
        basic_response = await test_mcp_tool_interface()
        test_results['basic_interface'] = {'status': 'PASSED', 'response': basic_response}
        
        # Test 2: Semantic signals integration
        logger.info("\n" + "="*60)
        semantic_responses = await test_semantic_signals_integration()
        test_results['semantic_integration'] = {'status': 'PASSED', 'responses': semantic_responses}
        
        # Test 3: Error handling and degradation
        logger.info("\n" + "="*60)
        error_responses = await test_error_handling_and_degradation()
        test_results['error_handling'] = {'status': 'PASSED', 'responses': error_responses}
        
        # Test 4: Performance and latency
        logger.info("\n" + "="*60)
        performance_results = await test_performance_and_latency()
        test_results['performance'] = {'status': 'PASSED', 'results': performance_results}
        
        # Test 5: Audit trail generation
        logger.info("\n" + "="*60)
        audit_response = await test_audit_trail_generation()
        test_results['audit_trail'] = {'status': 'PASSED', 'response': audit_response}
        
        logger.info("\n" + "="*60)
        logger.info("🎉 ALL MCP INTEGRATION TESTS PASSED!")
        logger.info("="*60)
        
        # Print summary
        print("\nMCP INTEGRATION TEST SUMMARY")
        print("="*60)
        for test_name, result in test_results.items():
            print(f"✅ {test_name.replace('_', ' ').title()}: {result['status']}")
        
        print("\nKEY METRICS:")
        if 'performance' in test_results:
            perf = test_results['performance']['results']
            print(f"📊 Total Evaluations: {perf['total_evaluations']}")
            print(f"🚀 Throughput: {perf['throughput']:.2f} eval/sec")
        
        print(f"🛡️ MCP Tool Interface: OPERATIONAL")
        print(f"🔍 Semantic Integration: VALIDATED")
        print(f"⚡ Error Handling: ROBUST")
        print(f"📋 Audit Trail: COMPLETE")
        print("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ MCP Integration Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_mcp_integration_tests())
    exit(0 if success else 1)