import os
import logging
import json
import asyncio
import threading
from datetime import datetime

from pathlib import Path
from a2a.types import AgentCard
from agent.guardial_secure import AbiGuardianSecure
from agent.emergency_response import get_emergency_response_system
from agent.dashboard import start_dashboard_server
from agent.alerting_system import get_alerting_system
from common.a2a_server import start_server

logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')

async def initialize_guardian_security():
    """
    CRITICAL: Initialize Guardian security and emergency systems before starting server
    
    This ensures the system cannot start without proper security validation
    """
    logger.info("🔒 Pre-flight security and emergency systems check...")
    
    # Initialize emergency response system first
    emergency_system = get_emergency_response_system()
    logger.info("✅ Emergency response system initialized")
    
    guardian = AbiGuardianSecure()
    
    # CRITICAL: Initialize and validate security
    security_ok = await guardian.initialize_security()
    
    if not security_ok:
        logger.error("🚨 CRITICAL: Guardian security initialization FAILED")
        logger.error("🚨 SYSTEM STARTUP BLOCKED - Security requirements not met")
        # Log emergency event for failed startup
        from agent.emergency_response import EmergencyType, EmergencyLevel
        try:
            await emergency_system.emergency_shutdown(
                reason="Guardian security initialization failed during startup",
                initiated_by="SYSTEM_STARTUP_FAILURE",
                emergency_type=EmergencyType.SYSTEM_COMPROMISE,
                emergency_level=EmergencyLevel.CRITICAL
            )
        except Exception as e:
            logger.error(f"Failed to log emergency shutdown: {e}")
        
        raise RuntimeError("CRITICAL SECURITY FAILURE: Guardian cannot start without valid security policies")
    
    logger.info("✅ Guardian security validation PASSED")
    logger.info("✅ Emergency response system ready")
    return guardian

def guardian_factory(agent_card_dir: AgentCard):
    """
    Factory function for creating Guardian agent with security validation
    """
    with Path.open(agent_card_dir) as file:
        data = json.load(file)
        agent_card = AgentCard(**data)
    
    if agent_card.name != "Abi Guardial Agent":
        logger.error(f'[!] Unexpected AgentCard name: {agent_card.name!r}')
        raise ValueError(f"Unexpected Agent card name: {agent_card.name!r}")
    
    # Create guardian instance (security will be validated during server startup)
    return AbiGuardianSecure()

async def secure_startup():
    """
    Secure startup sequence with mandatory security validation
    """
    try:
        # STEP 1: Initialize alerting system
        logger.info("🔔 Initializing alerting system...")
        alerting_system = get_alerting_system()
        
        # STEP 2: Start dashboard server in background thread
        dashboard_port = int(os.getenv("GUARDIAL_DASHBOARD_PORT", "8080"))
        dashboard_host = os.getenv("GUARDIAL_DASHBOARD_HOST", "0.0.0.0")
        
        logger.info(f"🚀 Starting security dashboard on {dashboard_host}:{dashboard_port}")
        dashboard_thread = threading.Thread(
            target=start_dashboard_server,
            args=(dashboard_host, dashboard_port),
            daemon=True
        )
        dashboard_thread.start()
        
        # STEP 3: Initialize and validate Guardian security
        logger.info("🛡️ Starting ABI Guardian Agent with Secure OPA...")
        guardian = await initialize_guardian_security()
        
        # STEP 4: Perform comprehensive health check
        health = await guardian.health_check()
        logger.info(f"🔍 Guardian Health Check: {health}")
        
        if health.get('overall_status') != 'SECURE_AND_OPERATIONAL':
            logger.error(f"🚨 CRITICAL: Guardian health check failed: {health}")
            
            # Send critical alert
            await alerting_system.send_alert({
                "alert_type": "Guardian Health Check Failed",
                "severity": "critical",
                "message": f"Guardian health check failed: {health}",
                "timestamp": datetime.utcnow().isoformat(),
                "metric_name": "health_check",
                "current_value": health.get('overall_status', 'UNKNOWN'),
                "threshold": "SECURE_AND_OPERATIONAL",
                "duration_seconds": 0,
                "system_status": "FAILED_STARTUP"
            })
            
            raise RuntimeError("Guardian health check failed - system not secure")
        
        # STEP 5: Send startup success alert
        await alerting_system.send_alert({
            "alert_type": "Guardian System Started",
            "severity": "info",
            "message": "Guardial security system started successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "metric_name": "system_startup",
            "current_value": "SUCCESS",
            "threshold": "SUCCESS",
            "duration_seconds": 0,
            "system_status": health.get('overall_status', 'OPERATIONAL')
        })
        
        # STEP 6: Start the main server (security is now validated)
        logger.info("✅ Security validation complete - Starting Guardian server...")
        logger.info(f"📊 Dashboard available at: http://{dashboard_host}:{dashboard_port}")
        start_server("0.0.0.0", 8003, agent_card_dir, guardian_factory)
        
    except Exception as e:
        logger.error(f"🚨 CRITICAL: Secure startup failed: {e}")
        logger.error("🚨 GUARDIAN AGENT STARTUP BLOCKED")
        
        # Send emergency alert if alerting system is available
        try:
            alerting_system = get_alerting_system()
            await alerting_system.send_emergency_alert({
                "emergency_type": "STARTUP_FAILURE",
                "emergency_level": "CRITICAL",
                "reason": f"Guardian startup failed: {str(e)}",
                "initiated_by": "SYSTEM_STARTUP",
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as alert_error:
            logger.error(f"Failed to send startup failure alert: {alert_error}")
        
        raise

if __name__ == '__main__':
    # Run secure startup sequence
    asyncio.run(secure_startup())