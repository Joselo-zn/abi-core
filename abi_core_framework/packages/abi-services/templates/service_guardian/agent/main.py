#!/usr/bin/env python3
"""Guardian Agent — Entry point.

Performs security initialization before starting the A2A server.
If security validation fails, the process exits with code 1.
"""

import asyncio

from abi_core.common.utils import abi_logging
from app import agent
from guardian import AbiGuardianAgent


async def _secure_startup(guardian: AbiGuardianAgent) -> bool:
    """Run security initialization before the agent starts."""
    abi_logging("🔒 Pre-startup security initialization...")

    security_ok = await guardian.initialize_security()
    if not security_ok:
        abi_logging("🚨 CRITICAL: Security validation FAILED — BLOCKED", level="error")
        return False

    health = await guardian.health_check()
    abi_logging(f"🔍 Health: {health.get('overall_status', 'UNKNOWN')}")

    if health.get("overall_status") != "SECURE_AND_OPERATIONAL":
        abi_logging(f"🚨 Health check failed: {health}", level="error")
        return False

    abi_logging("✅ Security validated — starting A2A server")
    return True


guardian = AbiGuardianAgent()

# Run security validation synchronously before agent.run()
loop = asyncio.new_event_loop()
try:
    secure = loop.run_until_complete(_secure_startup(guardian))
except Exception as e:
    abi_logging(f"🚨 Startup failed: {e}", level="error")
    secure = False
finally:
    loop.close()

if not secure:
    exit(1)

agent.run(guardian)
