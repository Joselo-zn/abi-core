import os
import logging
import json
import asyncio

from pathlib import Path
from a2a.types import AgentCard
from agent.guardial_secure import AbiGuardianSecure
from common.a2a_server import start_server

logger = logging.getLogger(__name__)

agent_card_dir = os.getenv('AGENT_CARD')

async def initialize_guardian_security():
    """
    CRITICAL: Initialize Guardian security before starting server
    
    This ensures the system cannot start without proper security validation
    """
    logger.info("🔒 Pre-flight security check...")
    
    guardian = AbiGuardianSecure()
    
    # CRITICAL: Initialize and validate security
    security_ok = await guardian.initialize_security()
    
    if not security_ok:
        logger.error("🚨 CRITICAL: Guardian security initialization FAILED")
        logger.error("🚨 SYSTEM STARTUP BLOCKED - Security requirements not met")
        raise RuntimeError("CRITICAL SECURITY FAILURE: Guardian cannot start without valid security policies")
    
    logger.info("✅ Guardian security validation PASSED")
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
        # STEP 1: Initialize and validate Guardian security
        logger.info("🛡️ Starting ABI Guardian Agent with Secure OPA...")
        guardian = await initialize_guardian_security()
        
        # STEP 2: Perform comprehensive health check
        health = await guardian.health_check()
        logger.info(f"🔍 Guardian Health Check: {health}")
        
        if health.get('overall_status') != 'SECURE_AND_OPERATIONAL':
            logger.error(f"🚨 CRITICAL: Guardian health check failed: {health}")
            raise RuntimeError("Guardian health check failed - system not secure")
        
        # STEP 3: Start the server (security is now validated)
        logger.info("✅ Security validation complete - Starting Guardian server...")
        start_server("0.0.0.0", 8003, agent_card_dir, guardian_factory)
        
    except Exception as e:
        logger.error(f"🚨 CRITICAL: Secure startup failed: {e}")
        logger.error("🚨 GUARDIAN AGENT STARTUP BLOCKED")
        raise

if __name__ == '__main__':
    # Run secure startup sequence
    asyncio.run(secure_startup())