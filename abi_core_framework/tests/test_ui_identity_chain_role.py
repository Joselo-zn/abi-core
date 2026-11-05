"""The Chat UI's identity chain carries the admin role, sealed with the rest.
The Orchestrator's quotas skip an admin (abi-swarm rate-limit.md).
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("chainlit")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("HOP_SECRET_CHATUI_ORCHESTRATOR", "hop-secret")
    from abi_core.ui import chainlit_app
    return chainlit_app


def _chain(app, monkeypatch, metadata):
    from chainlit.context import context_var
    user = SimpleNamespace(id="user-1", metadata=metadata)
    token = context_var.set(SimpleNamespace(session=SimpleNamespace(user=user, thread_id="thread-1")))
    try:
        return app._build_identity_chain()
    finally:
        context_var.reset(token)          # no session leaks into later tests


def test_an_admin_is_marked_in_the_sealed_chain(app, monkeypatch):
    from abi_core.security.identity_chain import get_id, verify_chain
    chain = _chain(app, monkeypatch, {"is_admin": True})
    assert verify_chain("hop-secret", chain) and get_id(chain, "role") == "admin"
    assert get_id(chain, "user_id") == "user-1" and get_id(chain, "thread_id") == "thread-1"


def test_a_regular_user_has_no_role_and_a_forged_one_does_not_verify(app, monkeypatch):
    from abi_core.security.identity_chain import get_id, verify_chain
    chain = _chain(app, monkeypatch, {})
    assert get_id(chain, "role") is None
    forged = chain + [{"id_type": "role", "id_value": "admin", "checksum": "0" * 64}]
    assert not verify_chain("hop-secret", forged)
