"""
ABI-Framework: Complete Multi-Agent AI Framework

This is the umbrella package that provides a clean, unified API
for all ABI components while maintaining backward compatibility.

Usage:
    # Traditional imports (still work)
    from abi_core.common.workflow import AgentInteractionFlow
    
    # New unified API
    from abi_framework import AgentInteractionFlow, AbiOrchestratorAgent
    
    # Backward compatibility aliases
    from abi_framework import AgentInteractionFlow as WorkflowGraph
"""

__version__ = "1.1.0"

# Re-export key components for clean API
try:
    # Core components
    from abi_core.common.workflow import AgentInteractionFlow, InteractionFlowNode, InteractionFlowState
    from abi_core.common.semantic_tools import tool_find_agent
    from abi_core.security.a2a_access_validator import A2AAccessValidator
    
    # Agents
    from abi_core.abi_agents.orchestrator.agent.orchestrator import AbiOrchestratorAgent
    from abi_core.abi_agents.planner.agent.planner import AbiPlannerAgent
    
    # Backward compatibility aliases
    WorkflowGraph = AgentInteractionFlow
    WorkflowNode = InteractionFlowNode
    WorkflowState = InteractionFlowState
    
    __all__ = [
        "AgentInteractionFlow",
        "InteractionFlowNode",
        "InteractionFlowState",
        "WorkflowGraph",  # Backward compatibility
        "WorkflowNode",   # Backward compatibility
        "WorkflowState",  # Backward compatibility
        "tool_find_agent", 
        "A2AAccessValidator",
        "AbiOrchestratorAgent",
        "AbiPlannerAgent"
    ]
    
except ImportError:
    # During migration, some imports might fail
    __all__ = []