"""Open WebUI requests: one session per verified user + chat; an identity
that is sent but cannot be verified is rejected, never made anonymous; the
unsigned user header is never trusted.

Spec: .abi/specs/implemented/openwebui-session.md
"""

import time

import jwt
import pytest

from abi_core.session.openwebui import (
    CHAT_ID_HEADER, USER_JWT_HEADER, OpenWebUIIdentityError, openwebui_context_id, verified_user_id,
)

SECRET = "s3cret"


def _token(sub="u1", secret=SECRET, iss="open-webui", exp_in=60):
    """Like Open WebUI's _mint_forward_user_jwt: HS256, sub, iss, exp."""
    now = int(time.time())
    return jwt.encode({"sub": sub, "iss": iss, "iat": now, "exp": now + exp_in,
                       "email": "a@b.c", "name": "A", "role": "user"}, secret, algorithm="HS256")


def _headers(token, chat="c1"):
    h = {USER_JWT_HEADER: token}
    if chat:
        h[CHAT_ID_HEADER] = chat
    return h


def test_valid_token():
    assert verified_user_id(_token(), SECRET) == "u1"


@pytest.mark.parametrize("token", [
    _token(secret="other"),            # signed with another secret
    _token(iss="someone-else"),        # another issuer
    _token(exp_in=-10),                # expired
    "not.a.jwt",
    "garbage",
])
def test_rejected_tokens(token):
    assert verified_user_id(token, SECRET) is None


def test_alg_none_rejected():
    unsigned = jwt.encode({"sub": "u1", "iss": "open-webui"}, key="", algorithm="none")
    assert verified_user_id(unsigned, SECRET) is None


def test_same_chat_same_session_other_chat_or_user_other_session():
    a = openwebui_context_id(_headers(_token("u1"), "c1"), SECRET)
    assert a == openwebui_context_id(_headers(_token("u1"), "c1"), SECRET)
    assert a != openwebui_context_id(_headers(_token("u1"), "c2"), SECRET)
    assert a != openwebui_context_id(_headers(_token("u2"), "c1"), SECRET)


def test_no_identity_sent_returns_none():
    assert openwebui_context_id({}, SECRET) is None
    assert openwebui_context_id({CHAT_ID_HEADER: "c1"}, SECRET) is None
    # The unsigned user header is ignored: it never yields a session.
    assert openwebui_context_id({CHAT_ID_HEADER: "c1", "X-OpenWebUI-User-Id": "u1"}, SECRET) is None


@pytest.mark.parametrize("headers, secret", [
    (_headers(_token()), None),                    # agent has no secret
    (_headers(_token(secret="forged")), SECRET),   # does not verify
    (_headers(_token(exp_in=-10)), SECRET),        # expired
    (_headers(_token(), chat=None), SECRET),       # no chat id
])
def test_identity_sent_but_unusable_raises(headers, secret):
    with pytest.raises(OpenWebUIIdentityError):
        openwebui_context_id(headers, secret)
