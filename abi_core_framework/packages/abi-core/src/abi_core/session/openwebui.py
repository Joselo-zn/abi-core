"""
Session for requests from Open WebUI (the Ollama-compatible /api/chat and
/api/generate routes of a generated web interface).

Open WebUI cannot build the identity chain the Chainlit UI sends to /stream.
Its equivalent is the JWT it signs when ``ENABLE_FORWARD_USER_INFO_HEADERS``
and ``FORWARD_USER_INFO_HEADER_JWT_SECRET`` are set: ``X-OpenWebUI-User-Jwt``
(HS256, the user id in ``sub``, issuer ``open-webui``) plus
``X-OpenWebUI-Chat-Id``. The agent verifies it with ``OPENWEBUI_JWT_SECRET``
(the same value as Open WebUI's ``FORWARD_USER_INFO_HEADER_JWT_SECRET``),
the role ``HOP_SECRET_*`` plays for the identity chain.

Same rule as the identity chain (identity-chain-hmac-contract.md, "no
silent degradation"): an identity that is sent but cannot be verified is
rejected, never turned into an anonymous session. The unsigned
``X-OpenWebUI-User-Id`` header is not accepted: anyone could claim to be
another user and enter their session. The chat id is not signed, which only
lets a verified user move between their own chats.

Spec: .abi/specs/implemented/openwebui-session.md
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Mapping, Optional

from abi_core.security.identity_chain import derive_session_id

CHAT_ID_HEADER = "X-OpenWebUI-Chat-Id"
USER_JWT_HEADER = "X-OpenWebUI-User-Jwt"
_ISSUER = "open-webui"


def _b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def verified_user_id(token: str, secret: str, now: Optional[float] = None) -> Optional[str]:
    """The ``sub`` of an HS256 JWT signed with ``secret`` by Open WebUI, or
    None if the token is malformed, signed differently, from another issuer,
    or expired."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        if header.get("alg") != "HS256":
            return None
        expected = hmac.new(secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if payload.get("iss") != _ISSUER:
        return None
    exp = payload.get("exp")
    if exp is not None and float(exp) < (now if now is not None else time.time()):
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


class OpenWebUIIdentityError(Exception):
    """An Open WebUI identity was sent but cannot be accepted (→ HTTP 401)."""


def openwebui_context_id(headers: Mapping[str, str], jwt_secret: Optional[str]) -> Optional[str]:
    """context_id for one verified Open WebUI user's chat:
    ``derive_session_id("openwebui", user, chat)``.

    None when no Open WebUI identity was sent (the caller goes on to the
    session token). Raises OpenWebUIIdentityError when one was sent and the
    agent has no secret, the JWT does not verify, or the chat id is missing.
    ``headers`` is case-insensitive in Starlette; a plain dict must use the
    header names as written above.
    """
    token = headers.get(USER_JWT_HEADER)
    if not token:
        return None
    if not jwt_secret:
        raise OpenWebUIIdentityError("Open WebUI identity sent, but OPENWEBUI_JWT_SECRET is not set")
    user_id = verified_user_id(token, jwt_secret)
    if not user_id:
        raise OpenWebUIIdentityError("Invalid or expired Open WebUI identity")
    chat_id = headers.get(CHAT_ID_HEADER)
    if not chat_id:
        raise OpenWebUIIdentityError("Open WebUI identity missing the chat id")
    return derive_session_id("openwebui", user_id, chat_id)
