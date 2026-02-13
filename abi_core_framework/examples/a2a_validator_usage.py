"""
Example: A2A Access Validator Usage

Demonstrates how to use the A2A access validator to control
agent-to-agent communication.
"""

import asyncio
from abi_core.security.a2a_access_validator import (
    validate_a2a_access,
    A2AAccessValidator,
    get_validator
)
from abi_core.common.agent_card_init import load_agent_card


# ============================================
# Example 1: Using the decorator
# ============================================

# Load agent cards
orchestrator_card = load_agent_card("path/to/orchestrator/agent_card.json")
data_agent_card = load_agent_card("path/to/data_agent/agent_card.json")


@validate_a2a_access(a2a=(orchestrator_card, data_agent_card))
async def send_message_to_data_agent(message: str):
    """
    Send message to data agent
    This function will only execute if A2A validation passes
    """
    print(f"Sending message to data agent: {message}")
    # Actual communication logic here
    return {"status": "success", "response": "Message received"}


async def example_decorator():
    """Example using decorator"""
    print("\n=== Example 1: Using Decorator ===")
    
    try:
        result = await send_message_to_data_agent("Process this data")
        print(f"✅ Success: {result}")
    except PermissionError as e:
        print(f"❌ Access denied: {e}")


# ============================================
# Example 2: Manual validation
# ============================================

async def example_manual_validation():
    """Example using manual validation"""
    print("\n=== Example 2: Manual Validation ===")
    
    # Get validator instance
    validator = get_validator()
    
    # Validate access
    is_allowed, reason = await validator.validate_a2a_access(
        source_agent_card=orchestrator_card,
        target_agent_card=data_agent_card,
        message="Hello from orchestrator",
        additional_context={"priority": "high", "task_id": "task-123"}
    )
    
    if is_allowed:
        print("✅ Communication allowed")
        # Proceed with communication
    else:
        print(f"❌ Communication denied: {reason}")


# ============================================
# Example 3: Custom validator configuration
# ============================================

async def example_custom_validator():
    """Example with custom validator configuration"""
    print("\n=== Example 3: Custom Validator ===")
    
    # Create custom validator
    validator = A2AAccessValidator(
        guardian_url="http://localhost:8383",
        validation_mode="permissive",  # or "strict" or "disabled"
        enable_audit_log=True
    )
    
    # Build context
    context = validator.build_a2a_context(
        source_agent_card=orchestrator_card,
        target_agent_card=data_agent_card,
        message="Test message",
        additional_context={"test": True}
    )
    
    print(f"Context built: {context}")
    
    # Validate
    is_allowed, reason = await validator.validate_a2a_access(
        source_agent_card=orchestrator_card,
        target_agent_card=data_agent_card,
        message="Test message"
    )
    
    print(f"Allowed: {is_allowed}, Reason: {reason}")


# ============================================
# Example 4: Multiple agent communications
# ============================================

async def example_multiple_communications():
    """Example with multiple agent communications"""
    print("\n=== Example 4: Multiple Communications ===")
    
    validator = get_validator()
    
    # Load multiple agent cards
    agents = {
        "orchestrator": orchestrator_card,
        "data_agent": data_agent_card,
        "planner": load_agent_card("path/to/planner/agent_card.json"),
    }
    
    # Test different communication pairs
    test_pairs = [
        ("orchestrator", "data_agent"),
        ("orchestrator", "planner"),
        ("data_agent", "planner"),
        ("planner", "orchestrator"),
    ]
    
    for source, target in test_pairs:
        is_allowed, reason = await validator.validate_a2a_access(
            source_agent_card=agents[source],
            target_agent_card=agents[target],
            message=f"Test from {source} to {target}"
        )
        
        status = "✅" if is_allowed else "❌"
        print(f"{status} {source} -> {target}: {reason or 'Allowed'}")


# ============================================
# Example 5: Error handling
# ============================================

async def example_error_handling():
    """Example with error handling"""
    print("\n=== Example 5: Error Handling ===")
    
    @validate_a2a_access(a2a=(orchestrator_card, data_agent_card))
    async def protected_function(message: str):
        return f"Processed: {message}"
    
    try:
        result = await protected_function("Important message")
        print(f"✅ Result: {result}")
    except PermissionError as e:
        print(f"❌ Permission denied: {e}")
        # Handle denial - maybe log, retry, or notify user
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


# ============================================
# Example 6: Using environment variables
# ============================================

async def example_env_config():
    """Example using environment variables for configuration"""
    print("\n=== Example 6: Environment Configuration ===")
    
    import os
    
    # Set environment variables
    os.environ["A2A_VALIDATION_MODE"] = "strict"
    os.environ["A2A_ENABLE_AUDIT_LOG"] = "true"
    os.environ["GUARDIAN_URL"] = "http://localhost:8383"
    
    # Validator will use these settings
    validator = get_validator()
    
    print(f"Validation mode: {validator.validation_mode}")
    print(f"Guardian URL: {validator.guardian_url}")
    print(f"Audit logging: {validator.enable_audit_log}")


# ============================================
# Run all examples
# ============================================

async def main():
    """Run all examples"""
    print("=" * 60)
    print("A2A Access Validator Examples")
    print("=" * 60)
    
    await example_decorator()
    await example_manual_validation()
    await example_custom_validator()
    await example_multiple_communications()
    await example_error_handling()
    await example_env_config()
    
    print("\n" + "=" * 60)
    print("Examples completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
