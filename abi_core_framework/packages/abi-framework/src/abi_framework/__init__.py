"""
ABI-Framework: Complete Multi-Agent AI Framework

This is the umbrella package that provides a clean, unified API
for all ABI components while maintaining backward compatibility.

Usage:
    # Traditional imports (still work)
    from abi_core.common.workflow import WorkflowGraph
    
    # New unified API
    from abi_framework import WorkflowGraph, AbiOrchestratorAgent
"""

__version__ = "1.1.0"

# Re-export key components for clean API
try:
    # Core components
    from abi_core.common.workflow import WorkflowGraph
    from abi_core.common.semantic_tools import tool_find_agent
    from abi_core.security.a2a_access_validator import A2AAccessValidator
    
    # Agents
    from abi_core.abi_agents.orchestrator.agent.orchestrator import AbiOrchestratorAgent
    from abi_core.abi_agents.planner.agent.planner import AbiPlannerAgent
    
    __all__ = [
        "WorkflowGraph",
        "tool_find_agent", 
        "A2AAccessValidator",
        "AbiOrchestratorAgent",
        "AbiPlannerAgent"
    ]
    
except ImportError:
    # During migration, some imports might fail
    __all__ = []