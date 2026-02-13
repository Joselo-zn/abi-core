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
                                                                            
                         █████╗   ██████╗   ██╗
                        ██╔══██╗  ██╔══██╗  ██║
                        ███████║  ██████╔╝  ██║
                        ██╔══██║  ██╔══██╗  ██║
                        ██║  ██║  ██████╔╝  ██║
                        ╚═╝  ╚═╝   ╚════╝   ╚═╝
         ___                    __     ____
        /   | ____ ____  ____  / /_   / __ )____ _________
       / /| |/ __ `/ _ \/ __ \/ __/  / __  / __ `/ ___/ _ \
      / ___ / /_/ /  __/ / / / /_   / /_/ / /_/ (__  )  __/
     /_/  |_\__, /\___/_/ /_/\__/  /_____/\__,_/____/\___/
    ____   /____/_                __                  __
   /  _/___  / __/________ ______/ /________  _______/ /___  __________
   / // __ \/ /_/ ___/ __ `/ ___/ __/ ___/ / / / ___/ __/ / / / ___/ _ \
 _/ // / / / __/ /  / /_/ (__  ) /_/ /  / /_/ / /__/ /_/ /_/ / /  /  __/
/___/_/ /_/_/ /_/   \__,_/____/\__/_/   \__,_/\___/\__/\__,_/_/   \___/
"""
ABI_BANNER += f""" 
ABI Framework - Agent-Based Infrastructure
OSS CLI v{ABI_CORE_VERSION}

Create, orchestrate and secure autonomous AI systems.
Powered by ABI Core v{ABI_CORE_VERSION}"""