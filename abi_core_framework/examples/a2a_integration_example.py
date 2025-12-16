"""
Example: Complete A2A Integration in Orchestrator

Demonstrates how A2A validation is automatically integrated
in the workflow system.
"""

import asyncio
from config import config, AGENT_CARD
from abi_core.common.workflow import WorkflowGraph, WorkflowNode
from abi_core.common.agent_card_init import load_agent_card


async def main():
    """Example of orchestrator using A2A validation"""
    
    print("=" * 60)
    print("A2A Integration Example")
    print("=" * 60)
    
    # Display current A2A configuration
    print(f"\n📋 A2A Configuration:")
    print(f"  Mode: {config.A2A_VALIDATION_MODE}")
    print(f"  Audit Log: {config.A2A_ENABLE_AUDIT_LOG}")
    print(f"  Guardian URL: {config.GUARDIAN_URL}")
    
    # Load agent cards
    print(f"\n🤖 Source Agent: {AGENT_CARD.name}")
    
    # Load target agents
    data_agent = load_agent_card("path/to/data_agent_card.json")
    analytics_agent = load_agent_card("path/to/analytics_agent_card.json")
    
    print(f"🎯 Target Agents:")
    print(f"  - {data_agent.name}")
    print(f"  - {analytics_agent.name}")
    
    # Create workflow
    print(f"\n🔧 Creating workflow...")
    workflow = WorkflowGraph()
    
    # Add nodes
    node1 = WorkflowNode(
        task="Extract data from database",
        agent_card=data_agent,
        node_key="extract_data"
    )
    workflow.add_node(node1)
    
    node2 = WorkflowNode(
        task="Analyze extracted data",
        agent_card=analytics_agent,
        node_key="analyze_data"
    )
    workflow.add_node(node2)
    
    # Add edge
    workflow.add_edge(node1.id, node2.id)
    
    # IMPORTANT: Set source card for A2A validation
    print(f"\n🔒 Configuring A2A validation...")
    workflow.set_source_card(AGENT_CARD)
    print(f"  Source: {AGENT_CARD.name}")
    print(f"  Validation will check:")
    print(f"    ✓ {AGENT_CARD.name} -> {data_agent.name}")
    print(f"    ✓ {AGENT_CARD.name} -> {analytics_agent.name}")
    
    # Set node attributes
    workflow.set_node_attributes(node1.id, {
        'query': 'Extract sales data from last month',
        'task_id': 'task-001',
        'context_id': 'ctx-001'
    })
    
    workflow.set_node_attributes(node2.id, {
        'query': 'Analyze sales trends',
        'task_id': 'task-002',
        'context_id': 'ctx-001'
    })
    
    # Execute workflow with automatic A2A validation
    print(f"\n🚀 Executing workflow...")
    print(f"  (A2A validation happens automatically)\n")
    
    try:
        async for chunk in workflow.run_workflow():
            # Process chunks
            if hasattr(chunk, 'root'):
                print(f"  📦 Received chunk from agent")
            
        print(f"\n✅ Workflow completed successfully!")
        print(f"  All A2A communications were validated")
        
    except PermissionError as e:
        print(f"\n❌ A2A Validation Failed!")
        print(f"  {e}")
        print(f"\n💡 Check:")
        print(f"  1. Guardian is running")
        print(f"  2. OPA policies allow this communication")
        print(f"  3. Agent cards are correctly configured")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 60)


async def example_manual_validation():
    """Example of manual A2A validation"""
    
    print("\n" + "=" * 60)
    print("Manual A2A Validation Example")
    print("=" * 60)
    
    from abi_core.security.a2a_access_validator import get_validator
    
    # Get validator (reads from config.py automatically)
    validator = get_validator()
    
    print(f"\n🔍 Validator Configuration:")
    print(f"  Mode: {validator.validation_mode}")
    print(f"  Guardian: {validator.guardian_url}")
    print(f"  Audit: {validator.enable_audit_log}")
    
    # Load cards
    target_card = load_agent_card("path/to/target_agent_card.json")
    
    # Manual validation
    print(f"\n🔒 Validating: {AGENT_CARD.name} -> {target_card.name}")
    
    is_allowed, reason = await validator.validate_a2a_access(
        source_agent_card=AGENT_CARD,
        target_agent_card=target_card,
        message="Test communication",
        additional_context={'test': True}
    )
    
    if is_allowed:
        print(f"✅ Communication allowed")
    else:
        print(f"❌ Communication denied: {reason}")
    
    print("=" * 60)


async def example_different_modes():
    """Example showing different validation modes"""
    
    print("\n" + "=" * 60)
    print("Validation Modes Example")
    print("=" * 60)
    
    from abi_core.security.a2a_access_validator import A2AAccessValidator
    
    target_card = load_agent_card("path/to/target_agent_card.json")
    
    modes = ['strict', 'permissive', 'disabled']
    
    for mode in modes:
        print(f"\n📋 Testing mode: {mode}")
        
        validator = A2AAccessValidator(
            validation_mode=mode,
            enable_audit_log=True
        )
        
        is_allowed, reason = await validator.validate_a2a_access(
            source_agent_card=AGENT_CARD,
            target_agent_card=target_card,
            message="Test message"
        )
        
        status = "✅ Allowed" if is_allowed else "❌ Denied"
        print(f"  {status}: {reason or 'No reason'}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run main example
    asyncio.run(main())
    
    # Run additional examples
    asyncio.run(example_manual_validation())
    asyncio.run(example_different_modes())
