"""abi_core.agent.failures: every error gets its kind (meta.error_code)."""

import pytest

from abi_core.agent import failures
from abi_core.agent.agent_response import AgentResponse


@pytest.mark.parametrize("text,code", [
    ("429 RESOURCE_EXHAUSTED: generativelanguage.googleapis.com quota exceeded", "provider_unavailable"),
    ("403 PERMISSION_DENIED billing account has an outstanding balance", "provider_unavailable"),
    ("A2A communication denied: Agent A -> Agent B. Reason: policy", "policy_denied"),
    ("could not build the reviewer", "internal"),
    ("Connection refused to ollama:11434", "provider_unavailable"),
    ("httpx.ConnectError: [Errno 111] Connection refused (http://localhost:11434/api/chat)", "provider_unavailable"),
    ("Connection refused to semantic-layer:10100", "internal"),
    ("", "internal"),
    (None, "internal"),
])
def test_classify(text, code):
    assert failures.classify(text) == code


def test_tag_keeps_codes_and_leaves_other_responses_alone():
    timeout = AgentResponse.error("took too long", code="timeout")
    assert failures.tag(timeout) is timeout
    result = AgentResponse.result({"status": "completed"})
    assert failures.tag(result) is result and failures.code_of(result) is None
    tagged = failures.tag(AgentResponse.error("Gemini model unavailable"))
    assert failures.code_of(tagged) == "provider_unavailable" and tagged["content"] == "Gemini model unavailable"
    assert failures.code_of(failures.tag(AgentResponse.error("boom"))) in failures.SYSTEM_CODES
    blocked = AgentResponse.error("Request blocked", code="request_blocked")
    assert failures.code_of(failures.tag(blocked)) not in failures.SYSTEM_CODES
