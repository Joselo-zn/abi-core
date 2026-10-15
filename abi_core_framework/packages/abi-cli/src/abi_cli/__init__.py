"""
ABI-CLI: Command line interface for ABI Framework
Provides project scaffolding and management tools
"""

try:
    from importlib.metadata import version as _version
    __version__ = _version("abi-core-ai")
except Exception:  # not installed as a distribution (e.g. a source checkout)
    __version__ = "unknown"