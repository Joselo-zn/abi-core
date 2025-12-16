# OPA Module for ABI
# Import modules lazily to avoid dependency issues

__all__ = ['get_opa_config', 'PolicyLoader', 'PolicyLoaderV2', 'CorePolicyGenerator']

def get_opa_config(*args, **kwargs):
    from .config import get_opa_config as _get_opa_config
    return _get_opa_config(*args, **kwargs)

def PolicyLoader(*args, **kwargs):
    from .policy_loader import PolicyLoader as _PolicyLoader
    return _PolicyLoader(*args, **kwargs)

def PolicyLoaderV2(*args, **kwargs):
    from .policy_loader_v2 import PolicyLoaderV2 as _PolicyLoaderV2
    return _PolicyLoaderV2(*args, **kwargs)

def CorePolicyGenerator(*args, **kwargs):
    from .core_policies import CorePolicyGenerator as _CorePolicyGenerator
    return _CorePolicyGenerator(*args, **kwargs)