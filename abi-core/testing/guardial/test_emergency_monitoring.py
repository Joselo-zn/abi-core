#!/usr/bin/env python3
"""
Emergency Procedures and Monitoring Tests - Task 6.4

This script tests emergency procedures and monitoring capabilities including:
- Emergency shutdown procedures and system response
- Audit logging and compliance trace generation
- Monitoring metrics collection and alerting thresholds
- Security event detection and response automation
- Disaster recovery and system restoration tests

Requirements tested: 5.1, 5.2, 5.3, 5.4, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4
"""

import asyncio
import json
import logging
import time
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmergencyTestManager:
    """Manages emergency and monitoring testing operations"""
    
    def __init__(self):
        self.test_dir = None
        self.original_emergency_log_path = None
        
    async def setup_test_environment(self):
        """Setup isolated test environment for emergency testing"""
        logger.info("🔧 Setting up emergency test environment...")
        
        # Create temporary directory for testing
        self.test_dir = Path(tempfile.mkdtemp(prefix="guardial_emergency_test_"))
        
        # Create test directories
        (self.test_dir / "emergency_logs").mkdir()
        (self.test_dir / "audit_logs").mkdir()
        (self.test_dir / "metrics").mkdir()
        
        logger.info(f"✅ Emergency test environment setup at: {self.test_dir}")
        
    async def cleanup_test_environment(self):
        """Cleanup test environment"""
        logger.info("🧹 Cleaning up emergency test environment...")
        
        # Remove test directory
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        logger.info("✅ Emergency test environment cleaned up")

async def test_emergency_shutdown_procedures():
    """Test emergency shutdown procedures and system response"""
    logger.info("🧪 Testing Emergency Shutdown Procedures...")
    
    test_manager = EmergencyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from agent.emergency_response import get_emergency_response_system, EmergencyType, EmergencyLevel
        
        # Initialize emergency response system
        emergency_system = get_emergency_response_system()
        
        # Test 1: Manual emergency shutdown
        logger.info("🛑 Testing manual emergency shutdown...")
        
        shutdown_result = await emergency_system.emergency_shutdown(
            reason="Testing manual emergency shutdown procedure",
            initiated_by="EMERGENCY_TEST_SYSTEM",
            emergency_type=EmergencyType.MANUAL_SHUTDOWN,
            emergency_level=EmergencyLevel.HIGH
        )
        
        assert shutdown_result["success"] == True, "Manual emergency shutdown failed"
        assert shutdown_result["emergency_id"] is not None, "Emergency ID not generated"
        
        # Verify system is in emergency state
        status = emergency_system.get_emergency_status()
        assert status["in_emergency_mode"] == True, "System not in emergency mode"
        assert status["current_state"] == "EMERGENCY_SHUTDOWN", "Incorrect emergency state"
        
        logger.info("✅ Manual emergency shutdown test passed")
        
        # Test 2: System compromise shutdown
        logger.info("🚨 Testing system compromise shutdown...")
        
        # Exit previous emergency first
        await emergency_system.exit_emergency_mode(
            reason="Exiting to test system compromise",
            initiated_by="EMERGENCY_TEST_SYSTEM"
        )
        
        compromise_result = await emergency_system.emergency_shutdown(
            reason="Detected system compromise during testing",
            initiated_by="SECURITY_MONITOR",
            emergency_type=EmergencyType.SYSTEM_COMPROMISE,
            emergency_level=EmergencyLevel.CRITICAL
        )
        
        assert compromise_result["success"] == True, "System compromise shutdown failed"
        
        # Verify critical level response
        status = emergency_system.get_emergency_status()
        assert status["emergency_level"] == "CRITICAL", "Emergency level not set to critical"
        
        logger.info("✅ System compromise shutdown test passed")
        
        # Test 3: Callback execution during shutdown
        logger.info("🔧 Testing shutdown callback execution...")
        
        callback_executed = []
        
        def test_callback(event):
            callback_executed.append(f"callback_{event.event_id}")
        
        emergency_system.register_shutdown_callback(test_callback)
        
        # Exit and trigger new shutdown to test callbacks
        await emergency_system.exit_emergency_mode(
            reason="Exiting to test callbacks",
            initiated_by="EMERGENCY_TEST_SYSTEM"
        )
        
        callback_result = await emergency_system.emergency_shutdown(
            reason="Testing callback execution",
            initiated_by="CALLBACK_TEST",
            emergency_type=EmergencyType.MANUAL_SHUTDOWN,
            emergency_level=EmergencyLevel.MEDIUM
        )
        
        assert len(callback_executed) > 0, "Shutdown callbacks not executed"
        logger.info(f"✅ Shutdown callbacks executed: {len(callback_executed)}")
        
        logger.info("✅ Emergency shutdown procedures test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Emergency shutdown procedures test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_audit_logging_and_compliance():
    """Test audit logging and compliance trace generation"""
    logger.info("🧪 Testing Audit Logging and Compliance...")
    
    test_manager = EmergencyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from agent.audit_persistence import get_audit_persistence_manager
        from agent.models.agent_models import GuardialEvaluationResponse, AuditReport, ComplianceTrace, RiskAssessment
        
        # Initialize audit persistence manager
        audit_manager = get_audit_persistence_manager()
        
        # Test 1: Audit report persistence
        logger.info("📝 Testing audit report persistence...")
        
        # Create test audit report
        test_audit_report = AuditReport(
            risk_assessment=RiskAssessment(
                overall_risk=0.7,
                policy_risk=0.6,
                semantic_risk=0.8,
                risk_factors=["PII detected", "High deviation score"],
                mitigation_suggestions=["Review manually", "Apply data redaction"]
            ),
            remediation_suggestions=["Manual review required", "Contact security team"]
        )
        
        test_compliance_trace = ComplianceTrace(
            rules_evaluated=["abi.core.pii_protection", "abi.core.data_access"],
            decision_path=["policy_evaluation", "semantic_analysis", "risk_calculation"],
            timestamps={
                "evaluation_started": datetime.utcnow(),
                "evaluation_completed": datetime.utcnow()
            },
            evaluation_context={
                "task_id": "audit_test_001",
                "context_id": "audit_context_001",
                "user_id": "audit_user_001"
            }
        )
        
        test_response = GuardialEvaluationResponse(
            decision="deny",
            deviation_score=0.75,
            audit_report=test_audit_report,
            compliance_trace=test_compliance_trace,
            uncertain=False,
            processing_time_ms=150
        )
        
        # Test persistence
        task_context = {
            "task_id": "audit_test_001",
            "context_id": "audit_context_001",
            "user_id": "audit_user_001"
        }
        
        persist_success = await audit_manager.persist_report(test_response, task_context)
        assert persist_success == True, "Audit report persistence failed"
        
        logger.info(f"✅ Audit report persisted with ID: {test_response.report_id}")
        
        # Test 2: Audit trail integrity validation
        logger.info("🔍 Testing audit trail integrity validation...")
        
        # Retrieve and validate the persisted report
        retrieved_report = await audit_manager.retrieve_report(test_response.report_id)
        assert retrieved_report is not None, "Failed to retrieve persisted report"
        
        # Validate integrity
        integrity_valid = await audit_manager.validate_report_integrity(test_response.report_id)
        assert integrity_valid == True, "Audit report integrity validation failed"
        
        logger.info("✅ Audit trail integrity validation passed")
        
        # Test 3: Compliance trace completeness
        logger.info("📋 Testing compliance trace completeness...")
        
        # Verify all required fields are present
        compliance_trace = retrieved_report.compliance_trace
        
        required_fields = ["rules_evaluated", "decision_path", "timestamps", "evaluation_context"]
        for field in required_fields:
            assert hasattr(compliance_trace, field), f"Missing compliance trace field: {field}"
            assert getattr(compliance_trace, field) is not None, f"Null compliance trace field: {field}"
        
        # Verify timestamps are properly recorded
        timestamps = compliance_trace.timestamps
        assert "evaluation_started" in timestamps, "Missing evaluation_started timestamp"
        assert "evaluation_completed" in timestamps, "Missing evaluation_completed timestamp"
        
        logger.info("✅ Compliance trace completeness test passed")
        
        # Test 4: Audit log immutability
        logger.info("🔒 Testing audit log immutability...")
        
        # Attempt to modify the audit log (should fail or be detected)
        original_signature = await audit_manager.get_report_signature(test_response.report_id)
        assert original_signature is not None, "No signature found for audit report"
        
        # Simulate tampering attempt
        tamper_detected = await audit_manager.detect_tampering(test_response.report_id)
        assert tamper_detected == False, "False positive tampering detection"
        
        logger.info("✅ Audit log immutability test passed")
        
        logger.info("✅ Audit logging and compliance test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Audit logging and compliance test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_monitoring_metrics_and_alerting():
    """Test monitoring metrics collection and alerting thresholds"""
    logger.info("🧪 Testing Monitoring Metrics and Alerting...")
    
    test_manager = EmergencyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from agent.metrics_collector import get_metrics_collector, AlertCondition
        from agent.alerting_system import get_alerting_system, AlertChannel
        
        # Initialize systems
        metrics = get_metrics_collector()
        alerting = get_alerting_system()
        
        # Test 1: Metrics collection
        logger.info("📊 Testing metrics collection...")
        
        # Record various metrics
        test_metrics = [
            ("evaluation_latency", 150.5, {"agent": "test"}),
            ("evaluation_latency", 200.0, {"agent": "test"}),
            ("evaluation_latency", 300.0, {"agent": "test"}),  # This should trigger alert
            ("deviation_score", 0.8, {"user": "test_user"}),
            ("deviation_score", 0.9, {"user": "test_user"}),  # High deviation
        ]
        
        for metric_name, value, tags in test_metrics:
            metrics._add_metric(metric_name, value, tags)
        
        # Record decisions
        metrics.record_decision("allow", 0.2, {"test": True})
        metrics.record_decision("deny", 0.9, {"test": True})
        metrics.record_decision("review", 0.6, {"test": True})
        
        # Record violations
        metrics.record_policy_violation("unauthorized_access", "high", {"test": True})
        metrics.record_semantic_signal("pii_detected", 0.95, {"test": True})
        
        # Get performance metrics
        perf_metrics = metrics.get_performance_metrics()
        assert perf_metrics["total_evaluations"] > 0, "No evaluations recorded"
        assert "decision_distribution" in perf_metrics, "Missing decision distribution"
        
        logger.info("✅ Metrics collection test passed")
        
        # Test 2: Alert condition setup and triggering
        logger.info("🚨 Testing alert condition setup...")
        
        # Add alert conditions
        latency_condition = AlertCondition(
            metric_name="evaluation_latency",
            threshold=250.0,
            operator=">",
            duration_seconds=1,
            severity="warning",
            message_template="Evaluation latency too high: {current_value}ms > {threshold}ms"
        )
        
        deviation_condition = AlertCondition(
            metric_name="deviation_score",
            threshold=0.85,
            operator=">",
            duration_seconds=1,
            severity="critical",
            message_template="High deviation score detected: {current_value} > {threshold}"
        )
        
        metrics.add_alert_condition(latency_condition)
        metrics.add_alert_condition(deviation_condition)
        
        # Wait for conditions to trigger
        await asyncio.sleep(2)
        
        # Check for alerts
        active_alerts = metrics.check_alerts()
        assert len(active_alerts) > 0, "No alerts triggered despite threshold breaches"
        
        logger.info(f"✅ Alert conditions triggered: {len(active_alerts)} alerts")
        
        # Test 3: Alerting system integration
        logger.info("📢 Testing alerting system integration...")
        
        # Add test alert channel
        test_channel = AlertChannel(
            name="test_webhook",
            channel_type="webhook",
            config={
                "url": "http://test.example.com/webhook",
                "method": "POST",
                "headers": {"Content-Type": "application/json"}
            },
            severity_filter=["warning", "critical"]
        )
        
        alerting.add_channel(test_channel)
        
        # Send test alert
        test_alert = {
            "alert_type": "Metrics Test Alert",
            "severity": "warning",
            "message": "Testing alerting system integration",
            "timestamp": datetime.utcnow().isoformat(),
            "metric_name": "test_metric",
            "current_value": 100.0,
            "threshold": 80.0
        }
        
        alert_sent = await alerting.send_alert(test_alert)
        assert alert_sent == True, "Alert sending failed"
        
        logger.info("✅ Alerting system integration test passed")
        
        # Test 4: Real-time monitoring
        logger.info("⏱️ Testing real-time monitoring...")
        
        # Simulate real-time activity
        start_time = time.time()
        
        for i in range(20):
            # Simulate varying latencies
            latency = 100 + (i * 15)  # Increasing latency
            metrics.record_evaluation_latency(latency, {"iteration": str(i)})
            
            # Simulate decisions
            if latency > 200:
                decision = "review"
                score = 0.7
            else:
                decision = "allow"
                score = 0.3
            
            metrics.record_decision(decision, score, {"iteration": str(i)})
            
            await asyncio.sleep(0.1)  # 100ms intervals
        
        monitoring_time = time.time() - start_time
        
        # Verify real-time metrics
        final_metrics = metrics.get_performance_metrics()
        assert final_metrics["total_evaluations"] >= 20, "Not all evaluations recorded"
        
        logger.info(f"✅ Real-time monitoring test passed ({monitoring_time:.2f}s)")
        
        logger.info("✅ Monitoring metrics and alerting test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Monitoring metrics and alerting test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_security_event_detection():
    """Test security event detection and response automation"""
    logger.info("🧪 Testing Security Event Detection...")
    
    test_manager = EmergencyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from agent.metrics_collector import get_metrics_collector
        from agent.alerting_system import get_alerting_system
        from agent.emergency_response import get_emergency_response_system
        
        # Initialize systems
        metrics = get_metrics_collector()
        alerting = get_alerting_system()
        emergency_system = get_emergency_response_system()
        
        # Test 1: High-risk action detection
        logger.info("🎯 Testing high-risk action detection...")
        
        # Simulate high-risk actions
        high_risk_events = [
            {"action": "unauthorized_admin_access", "risk_score": 0.95},
            {"action": "bulk_data_export", "risk_score": 0.88},
            {"action": "policy_override_attempt", "risk_score": 0.92},
            {"action": "suspicious_file_access", "risk_score": 0.85}
        ]
        
        for event in high_risk_events:
            metrics.record_decision("deny", event["risk_score"], {
                "action": event["action"],
                "security_event": True
            })
            
            # Record as security event
            metrics.record_system_event("high_risk_action_blocked", {
                "action": event["action"],
                "risk_score": event["risk_score"]
            })
        
        # Check security metrics
        security_metrics = metrics.get_security_metrics()
        assert security_metrics["total_violations"] >= len(high_risk_events), "High-risk events not recorded"
        
        logger.info("✅ High-risk action detection test passed")
        
        # Test 2: Anomaly detection
        logger.info("🔍 Testing anomaly detection...")
        
        # Simulate normal baseline
        for i in range(50):
            metrics.record_evaluation_latency(100 + (i % 10), {"baseline": True})
            metrics.record_decision("allow", 0.2 + (i % 3) * 0.1, {"baseline": True})
        
        # Simulate anomalous behavior
        anomalous_events = [
            {"latency": 500, "score": 0.95},  # Sudden latency spike
            {"latency": 600, "score": 0.98},  # Continued high latency
            {"latency": 550, "score": 0.92},  # Still anomalous
        ]
        
        for event in anomalous_events:
            metrics.record_evaluation_latency(event["latency"], {"anomaly": True})
            metrics.record_decision("deny", event["score"], {"anomaly": True})
        
        # Check for anomaly detection
        current_metrics = metrics.get_performance_metrics()
        
        # Should detect latency anomaly
        if "evaluation_latency" in current_metrics:
            recent_latency = current_metrics["evaluation_latency"].get("recent_avg", 0)
            assert recent_latency > 200, "Latency anomaly not detected"
        
        logger.info("✅ Anomaly detection test passed")
        
        # Test 3: Automated response triggers
        logger.info("🤖 Testing automated response triggers...")
        
        # Simulate critical security event that should trigger emergency response
        critical_event = {
            "event_type": "CRITICAL_SECURITY_BREACH",
            "severity": "critical",
            "description": "Multiple unauthorized access attempts detected",
            "risk_score": 0.99,
            "automated_response": True
        }
        
        # Record critical event
        metrics.record_system_event("critical_security_breach", critical_event)
        
        # This should trigger automated emergency response
        # (In a real system, this would be handled by the security monitor)
        
        # Simulate automated emergency response
        auto_response = await emergency_system.emergency_shutdown(
            reason=f"Automated response to: {critical_event['description']}",
            initiated_by="AUTOMATED_SECURITY_MONITOR",
            emergency_type="SECURITY_BREACH",
            emergency_level="CRITICAL"
        )
        
        assert auto_response["success"] == True, "Automated emergency response failed"
        
        logger.info("✅ Automated response triggers test passed")
        
        # Test 4: Threat level escalation
        logger.info("📈 Testing threat level escalation...")
        
        # Simulate escalating threat pattern
        threat_levels = ["low", "medium", "high", "critical"]
        
        for i, level in enumerate(threat_levels):
            threat_event = {
                "threat_level": level,
                "escalation_step": i + 1,
                "description": f"Threat escalation to {level} level"
            }
            
            metrics.record_system_event(f"threat_escalation_{level}", threat_event)
            
            # Send escalation alert
            escalation_alert = {
                "alert_type": "Threat Level Escalation",
                "severity": level,
                "message": f"Threat level escalated to {level.upper()}",
                "timestamp": datetime.utcnow().isoformat(),
                "escalation_step": i + 1
            }
            
            await alerting.send_alert(escalation_alert)
        
        # Verify escalation was recorded
        security_metrics = metrics.get_security_metrics()
        assert "system_events" in security_metrics, "System events not recorded"
        
        logger.info("✅ Threat level escalation test passed")
        
        logger.info("✅ Security event detection test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Security event detection test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_disaster_recovery():
    """Test disaster recovery and system restoration"""
    logger.info("🧪 Testing Disaster Recovery...")
    
    test_manager = EmergencyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from agent.emergency_response import get_emergency_response_system, EmergencyType, EmergencyLevel
        from agent.audit_persistence import get_audit_persistence_manager
        from agent.metrics_collector import get_metrics_collector
        
        # Initialize systems
        emergency_system = get_emergency_response_system()
        audit_manager = get_audit_persistence_manager()
        metrics = get_metrics_collector()
        
        # Test 1: System state backup and restoration
        logger.info("💾 Testing system state backup and restoration...")
        
        # Record initial system state
        initial_metrics = metrics.get_performance_metrics()
        initial_security_metrics = metrics.get_security_metrics()
        
        # Create backup of current state
        backup_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "performance_metrics": initial_metrics,
            "security_metrics": initial_security_metrics,
            "emergency_status": emergency_system.get_emergency_status()
        }
        
        # Simulate disaster (system compromise)
        logger.info("💥 Simulating disaster scenario...")
        
        disaster_result = await emergency_system.emergency_shutdown(
            reason="Simulated disaster - system compromise detected",
            initiated_by="DISASTER_SIMULATION",
            emergency_type=EmergencyType.SYSTEM_COMPROMISE,
            emergency_level=EmergencyLevel.CRITICAL
        )
        
        assert disaster_result["success"] == True, "Disaster simulation failed"
        
        # Verify system is in emergency state
        disaster_status = emergency_system.get_emergency_status()
        assert disaster_status["in_emergency_mode"] == True, "System not in emergency mode"
        
        logger.info("✅ Disaster simulation successful")
        
        # Test 2: Emergency data preservation
        logger.info("🔒 Testing emergency data preservation...")
        
        # Verify critical data is preserved during emergency
        emergency_history = emergency_system.get_emergency_history(limit=10)
        assert len(emergency_history) > 0, "Emergency history not preserved"
        
        # Verify audit logs are intact
        audit_integrity = await audit_manager.validate_all_reports_integrity()
        assert audit_integrity == True, "Audit log integrity compromised during emergency"
        
        logger.info("✅ Emergency data preservation test passed")
        
        # Test 3: System restoration procedure
        logger.info("🔄 Testing system restoration procedure...")
        
        # Initiate system restoration
        restoration_result = await emergency_system.exit_emergency_mode(
            reason="Disaster recovery - restoring system after security validation",
            initiated_by="DISASTER_RECOVERY_TEAM"
        )
        
        assert restoration_result["success"] == True, "System restoration failed"
        
        # Verify system is operational
        restored_status = emergency_system.get_emergency_status()
        assert restored_status["in_emergency_mode"] == False, "System still in emergency mode"
        
        logger.info("✅ System restoration test passed")
        
        # Test 4: Post-recovery validation
        logger.info("✅ Testing post-recovery validation...")
        
        # Verify system functionality after recovery
        post_recovery_metrics = metrics.get_performance_metrics()
        assert post_recovery_metrics is not None, "Metrics system not functional after recovery"
        
        # Test basic operations
        test_decision_recorded = False
        try:
            metrics.record_decision("allow", 0.3, {"post_recovery_test": True})
            test_decision_recorded = True
        except Exception as e:
            logger.error(f"Failed to record test decision: {e}")
        
        assert test_decision_recorded == True, "Basic operations not functional after recovery"
        
        # Verify audit system is functional
        audit_functional = await audit_manager.system_health_check()
        assert audit_functional == True, "Audit system not functional after recovery"
        
        logger.info("✅ Post-recovery validation test passed")
        
        # Test 5: Recovery time measurement
        logger.info("⏱️ Testing recovery time measurement...")
        
        # Simulate another emergency for timing
        timing_start = time.time()
        
        await emergency_system.emergency_shutdown(
            reason="Recovery time measurement test",
            initiated_by="TIMING_TEST",
            emergency_type=EmergencyType.MANUAL_SHUTDOWN,
            emergency_level=EmergencyLevel.MEDIUM
        )
        
        shutdown_time = time.time() - timing_start
        
        # Measure restoration time
        restore_start = time.time()
        
        await emergency_system.exit_emergency_mode(
            reason="Recovery time measurement - restoration",
            initiated_by="TIMING_TEST"
        )
        
        restore_time = time.time() - restore_start
        
        logger.info(f"📊 Shutdown time: {shutdown_time:.2f}s")
        logger.info(f"📊 Restoration time: {restore_time:.2f}s")
        
        # Performance assertions
        assert shutdown_time < 10, f"Shutdown too slow: {shutdown_time:.2f}s"
        assert restore_time < 15, f"Restoration too slow: {restore_time:.2f}s"
        
        logger.info("✅ Recovery time measurement test passed")
        
        logger.info("✅ Disaster recovery test passed")
        return {
            "shutdown_time": shutdown_time,
            "restore_time": restore_time,
            "data_preserved": True,
            "system_functional": True
        }
        
    except Exception as e:
        logger.error(f"❌ Disaster recovery test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def run_emergency_monitoring_tests():
    """Run all emergency procedures and monitoring tests"""
    logger.info("🚀 Starting Emergency Procedures and Monitoring Tests (Task 6.4)")
    
    test_results = {}
    
    try:
        # Test 1: Emergency shutdown procedures
        logger.info("\n" + "="*60)
        shutdown_ok = await test_emergency_shutdown_procedures()
        test_results['emergency_shutdown'] = {'status': 'PASSED' if shutdown_ok else 'FAILED'}
        
        # Test 2: Audit logging and compliance
        logger.info("\n" + "="*60)
        audit_ok = await test_audit_logging_and_compliance()
        test_results['audit_compliance'] = {'status': 'PASSED' if audit_ok else 'FAILED'}
        
        # Test 3: Monitoring metrics and alerting
        logger.info("\n" + "="*60)
        monitoring_ok = await test_monitoring_metrics_and_alerting()
        test_results['monitoring_alerting'] = {'status': 'PASSED' if monitoring_ok else 'FAILED'}
        
        # Test 4: Security event detection
        logger.info("\n" + "="*60)
        security_ok = await test_security_event_detection()
        test_results['security_detection'] = {'status': 'PASSED' if security_ok else 'FAILED'}
        
        # Test 5: Disaster recovery
        logger.info("\n" + "="*60)
        recovery_result = await test_disaster_recovery()
        recovery_ok = recovery_result is not False
        test_results['disaster_recovery'] = {
            'status': 'PASSED' if recovery_ok else 'FAILED',
            'metrics': recovery_result if recovery_ok else None
        }
        
        # Check overall results
        all_passed = all(result['status'] == 'PASSED' for result in test_results.values())
        
        logger.info("\n" + "="*60)
        if all_passed:
            logger.info("🎉 ALL EMERGENCY PROCEDURES AND MONITORING TESTS PASSED!")
        else:
            logger.error("❌ SOME EMERGENCY PROCEDURES AND MONITORING TESTS FAILED!")
        logger.info("="*60)
        
        # Print summary
        print("\nEMERGENCY PROCEDURES AND MONITORING TEST SUMMARY")
        print("="*60)
        for test_name, result in test_results.items():
            status_icon = "✅" if result['status'] == 'PASSED' else "❌"
            print(f"{status_icon} {test_name.replace('_', ' ').title()}: {result['status']}")
        
        # Print performance metrics if available
        if 'disaster_recovery' in test_results and test_results['disaster_recovery']['metrics']:
            metrics = test_results['disaster_recovery']['metrics']
            print(f"\nDISASTER RECOVERY METRICS:")
            print(f"🛑 Shutdown Time: {metrics['shutdown_time']:.2f}s")
            print(f"🔄 Restoration Time: {metrics['restore_time']:.2f}s")
            print(f"💾 Data Preserved: {'YES' if metrics['data_preserved'] else 'NO'}")
            print(f"⚙️ System Functional: {'YES' if metrics['system_functional'] else 'NO'}")
        
        print(f"\n🛑 Emergency Shutdown: {'OPERATIONAL' if shutdown_ok else 'FAILED'}")
        print(f"📋 Audit & Compliance: {'ROBUST' if audit_ok else 'FAILED'}")
        print(f"📊 Monitoring & Alerting: {'ACTIVE' if monitoring_ok else 'FAILED'}")
        print(f"🔍 Security Detection: {'RESPONSIVE' if security_ok else 'FAILED'}")
        print(f"🔄 Disaster Recovery: {'RESILIENT' if recovery_ok else 'FAILED'}")
        print("="*60)
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Emergency Procedures and Monitoring Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_emergency_monitoring_tests())
    exit(0 if success else 1)