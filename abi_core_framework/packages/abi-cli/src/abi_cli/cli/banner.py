import os

try:
    from importlib import metadata as _metadata
except Exception:
    try:
        import importlib_metadata as _metadata
    except Exception:
        _metadata = None


def _pkg_version():
    if _metadata:
        for name in ('abi-core-ai', 'abi-core', 'abi_core'):
            try:
                return _metadata.version(name)
            except Exception:
                pass
    try:
        import abi_core as _abi
        v = getattr(_abi, "__version__", None)
        if v:
            return v
    except Exception:
        pass
    return "unknown"


ABI_CORE_VERSION = _pkg_version()

ABI_BANNER = r"""
[bold bright_cyan]
                         █████═╗  ██████╗   ██╗
                        ██╔══██║  ██╔══██╗  ██║
                        ███████║  ██████╔╝  ██║
                        ██╔══██║  ██╔══██╗  ██║
                        ██║  ██║  ██████╔╝  ██║
                        ╚═╝  ╚═╝   ╚════╝   ╚═╝[/bold bright_cyan]
"""
ABI_BANNER += f"""[bold white]ABI Swarm[/bold white] [dim]— Self-Building Multi-Agent System[/dim]
[dim]OSS CLI v{ABI_CORE_VERSION} | Core v{ABI_CORE_VERSION}[/dim]
"""