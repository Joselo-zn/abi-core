"""
ABI-Services: Core services for ABI Framework
Provides semantic layer and service templates
"""

__version__ = "1.1.0"

# Lazy imports for services
def __getattr__(name):
    if name == "semantic":
        from . import semantic
        return semantic
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")