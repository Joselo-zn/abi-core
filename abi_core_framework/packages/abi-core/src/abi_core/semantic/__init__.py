"""
ABI Core Semantic Layer Module

This module provides semantic access validation and related utilities.
"""

from .semantic_access_validator import validate_semantic_access, SemanticAccessValidator

__all__ = [
    "validate_semantic_access",
    "SemanticAccessValidator",
]