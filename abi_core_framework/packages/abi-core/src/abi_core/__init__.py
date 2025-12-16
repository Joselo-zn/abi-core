"""
ABI-Core: Base libraries for ABI Framework
Provides core functionality for multi-agent systems
"""

__version__ = "1.1.0"

# Lazy imports to avoid dependency issues during migration
def __getattr__(name):
    if name == "common":
        from . import common
        return common
    elif name == "security":
        from . import security
        return security
    elif name == "opa":
        from . import opa
        return opa
    elif name == "abi_mcp":
        from . import abi_mcp
        return abi_mcp
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")