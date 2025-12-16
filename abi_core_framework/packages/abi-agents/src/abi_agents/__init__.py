"""
ABI-Agents: Built-in agents for ABI Framework
Provides orchestrator and planner agents
"""

__version__ = "1.1.0"

# Lazy imports for agents
def __getattr__(name):
    if name == "orchestrator":
        from . import orchestrator
        return orchestrator
    elif name == "planner":
        from . import planner
        return planner
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")