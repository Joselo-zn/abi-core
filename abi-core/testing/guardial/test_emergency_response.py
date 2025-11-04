#!/usr/bin/env python3
"""
Test script for Emergency Response System

This script tests the emergency response capabilities including:
- Emergency shutdown mechanisms
- Emergency mode operations
- Administrative overrides
- Event logging and integrity validation

Usage: python test_emergency_response.py
"""

import asyncio
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_emergency_response():
    """Test emergency response system functionality"""
    
    try:
        # Import emergency response system
        from agent.emergency_response import get_emergency_response_system, EmergencyType, EmergencyLevel
        
        logger.info("🧪 Starting Emergency Response System Tests")
        
        # Initialize emergency system
        emergency_system = get_emergency_response_system()
        logger.info("✅ Emergency response system initialized")
        
        # Test 1: Get initial status
        logger.info("\n📊 Test 1: Initial System Status")
        status = emergency_system.get_emergency_status()
        logger.info(f"Initial status: {json.dumps(status, indent=2)}")
        
        # Test 2: Enter emergency mode
        logger.info("\n🚨 Test 2: Enter Emergency Mode")
        result = await emergency_system.enter_emergency_mode(
            reason="Testing emergency mode functionality",
            initiated_by="TEST_SCRIPT",
            duration_hours=1  # Auto-exit after 1 hour
        )
        logger.info(f"Emergency mode result: {json.dumps(result, indent=2)}")
        
        # Test 3: Check status in emergency mode
        logger.info("\n📊 Test 3: Status in Emergency Mode")
        status = emergency_system.get_emergency_status()
        logger.info(f"Emergency mode status: {json.dumps(status, indent=2)}")
        
        # Test 4: Administrative override
        logger.info("\n🔐 Test 4: Administrative Override")
        override_result = await emergency_system.administrative_override(
            admin_id="TEST_ADMIN",
            override_reason="Testing administrative override functionality",
            original_decision={"allow": False, "deny": True, "risk_score": 0.9},
            override_decision={"allow": True, "deny": False, "risk_score": 0.1},
            justification="Override for testing purposes - demonstrating emergency capabilities",
            approval_chain=["TEST_ADMIN", "TEST_SUPERVISOR"]
        )
        logger.info(f"Override result: {json.dumps(override_result, indent=2)}")
        
        # Test 5: Exit emergency mode
        logger.info("\n✅ Test 5: Exit Emergency Mode")
        exit_result = await emergency_system.exit_emergency_mode(
            reason="Testing completed successfully",
            initiated_by="TEST_SCRIPT"
        )
        logger.info(f"Exit emergency mode result: {json.dumps(exit_result, indent=2)}")
        
        # Test 6: Emergency shutdown (this will put system in shutdown state)
        logger.info("\n🛑 Test 6: Emergency Shutdown")
        shutdown_result = await emergency_system.emergency_shutdown(
            reason="Testing emergency shutdown functionality",
            initiated_by="TEST_SCRIPT",
            emergency_type=EmergencyType.MANUAL_SHUTDOWN,
            emergency_level=EmergencyLevel.HIGH
        )
        logger.info(f"Shutdown result: {json.dumps(shutdown_result, indent=2)}")
        
        # Test 7: Get emergency history
        logger.info("\n📚 Test 7: Emergency History")
        history = emergency_system.get_emergency_history(limit=10)
        logger.info(f"Emergency history: {json.dumps(history, indent=2)}")
        
        # Test 8: Validate emergency integrity
        logger.info("\n🔍 Test 8: Emergency Log Integrity Validation")
        integrity = await emergency_system.validate_emergency_integrity()
        logger.info(f"Integrity validation: {json.dumps(integrity, indent=2)}")
        
        # Test 9: Final status check
        logger.info("\n📊 Test 9: Final System Status")
        final_status = emergency_system.get_emergency_status()
        logger.info(f"Final status: {json.dumps(final_status, indent=2)}")
        
        logger.info("\n✅ All Emergency Response System Tests Completed Successfully!")
        
        # Summary
        logger.info("\n📋 Test Summary:")
        logger.info(f"   - Total emergency events: {len(emergency_system.emergency_events)}")
        logger.info(f"   - Total admin overrides: {len(emergency_system.admin_overrides)}")
        logger.info(f"   - Current system state: {emergency_system.current_state.value}")
        logger.info(f"   - Emergency logs location: {emergency_system.emergency_log_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Emergency Response System Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_shutdown_callbacks():
    """Test shutdown callback registration and execution"""
    
    logger.info("\n🔧 Testing Shutdown Callbacks")
    
    try:
        from agent.emergency_response import get_emergency_response_system, EmergencyType, EmergencyLevel
        
        emergency_system = get_emergency_response_system()
        
        # Register test callbacks
        callback_executed = []
        
        def sync_callback(event):
            callback_executed.append(f"sync_callback_{event.event_id}")
            logger.info(f"🔧 Sync callback executed for event: {event.event_id}")
        
        async def async_callback(event):
            callback_executed.append(f"async_callback_{event.event_id}")
            logger.info(f"🔧 Async callback executed for event: {event.event_id}")
        
        # Register callbacks
        emergency_system.register_shutdown_callback(sync_callback)
        emergency_system.register_shutdown_callback(async_callback)
        
        logger.info(f"Registered {len(emergency_system.shutdown_callbacks)} shutdown callbacks")
        
        # Trigger shutdown to test callbacks
        result = await emergency_system.emergency_shutdown(
            reason="Testing shutdown callbacks",
            initiated_by="CALLBACK_TEST",
            emergency_type=EmergencyType.MANUAL_SHUTDOWN,
            emergency_level=EmergencyLevel.MEDIUM
        )
        
        logger.info(f"Callbacks executed: {callback_executed}")
        logger.info("✅ Shutdown callback test completed")
        
        return len(callback_executed) == 2
        
    except Exception as e:
        logger.error(f"❌ Shutdown callback test failed: {e}")
        return False

def main():
    """Main test function"""
    
    logger.info("🚀 Starting Emergency Response System Test Suite")
    
    async def run_tests():
        # Test basic emergency response functionality
        test1_result = await test_emergency_response()
        
        # Test shutdown callbacks
        test2_result = await test_shutdown_callbacks()
        
        # Overall result
        if test1_result and test2_result:
            logger.info("\n🎉 ALL TESTS PASSED - Emergency Response System is fully functional!")
            return True
        else:
            logger.error("\n❌ SOME TESTS FAILED - Check logs for details")
            return False
    
    # Run the tests
    result = asyncio.run(run_tests())
    
    if result:
        logger.info("\n✅ Emergency Response System Test Suite: PASSED")
        exit(0)
    else:
        logger.error("\n❌ Emergency Response System Test Suite: FAILED")
        exit(1)

if __name__ == "__main__":
    main()