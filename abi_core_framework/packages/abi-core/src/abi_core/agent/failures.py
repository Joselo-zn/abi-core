"""What kind of failure ended a run: ``meta.error_code`` on every error.

A client (the Chat UI) writes its own text from the code, in the user's
language (abi_core.ui.run_progress.error_message), and can react to it
(the ``ui.on_run_end`` extension hook receives it). Codes:

- ``timeout``               set at the source (HeartbeatTimeoutError), kept;
- ``request_blocked``       the request itself was refused (a content gate):
                            not the system's fault; set it at the source with
                            ``AgentResponse.error(msg, code="request_blocked")``;
- ``provider_unavailable``  the model provider failed (quota, billing,
                            permission, unavailable);
- ``policy_denied``         a policy denied a call (OPA, A2A);
- ``internal``              any other failure of the system.

``SYSTEM_CODES`` are the failures of the system (not of the request).

An agent with many error paths classifies the errors that carry no code in
one place, where its stream leaves (``tag`` on every chunk): some errors
only have their text (an error from another agent comes back as a string).

Usage::

    from abi_core.agent import failures

    async for chunk in agent.stream(query, context_id, task_id):
        chunk = failures.tag(chunk)
        if failures.code_of(chunk) in failures.SYSTEM_CODES:
            ...  # e.g. give back a quota the turn took
        yield chunk
"""

import re
from typing import Optional

SYSTEM_CODES = ("provider_unavailable", "policy_denied", "internal")

_PROVIDER = re.compile(
    r"generativelanguage|gemini|google\.genai|RESOURCE_EXHAUSTED|quota|billing|rate.?limit|\b429\b|"
    r"model (?:is )?(?:unavailable|overloaded)|\b503\b|UNAVAILABLE|API key not valid|LLM (?:call|provider)|"
    r"ollama|:11434\b",
    re.IGNORECASE)
_POLICY = re.compile(r"A2A communication denied|policy denied|denied by policy|\bOPA\b|not allowed by policy",
                     re.IGNORECASE)


def classify(text: Optional[str]) -> str:
    """The kind of a failure from its text: policy_denied,
    provider_unavailable or internal."""
    text = text or ""
    if _POLICY.search(text):
        return "policy_denied"
    if _PROVIDER.search(text):
        return "provider_unavailable"
    return "internal"


def tag(chunk):
    """The same chunk; an error without ``meta.error_code`` gets one."""
    if not isinstance(chunk, dict) or chunk.get("response_type") != "error":
        return chunk
    meta = chunk.get("meta") if isinstance(chunk.get("meta"), dict) else {}
    if meta.get("error_code"):
        return chunk
    return {**chunk, "meta": {**meta, "error_code": classify(str(chunk.get("content") or ""))}}


def code_of(chunk) -> Optional[str]:
    """The ``error_code`` of an error chunk, or None."""
    if isinstance(chunk, dict) and chunk.get("response_type") == "error":
        return ((chunk.get("meta") or {}).get("error_code")) or None
    return None
