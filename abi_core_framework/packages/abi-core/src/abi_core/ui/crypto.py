"""Application-level encryption for the Chat UI's data.

Envelope encryption: a key-encryption key (KEK) wraps one data key (DEK)
per user; DEKs encrypt the content with AES-256-GCM. Deleting a user's DEK
makes all their data unreadable (crypto-shredding) without deleting rows.

KEK, in order:
    ABI_UI_KMS_KEY    Cloud KMS key (projects/…/locations/…/keyRings/…/cryptoKeys/…).
                      Needs abi-core-ai[gcp] (google-auth); the service account
                      needs roles/cloudkms.cryptoKeyEncrypterDecrypter on it.
    ABI_UI_LOCAL_KEK  32 bytes, base64 — local development only.
    neither           encryption is off (local only); a warning is logged.

    ABI_UI_IDENTITY_KEY  secret for the deterministic HMAC of emails, so a
                         user is found by email without storing it.

Ciphertext: "enc:v1:<key id>:<base64(nonce ‖ ciphertext)>". The key id is
the DEK's owner (a user id, or "system"), so a value is decrypted without
knowing which row or user it came from. Values without the prefix are
returned as they are: rows written before encryption keep working.

Spec: .abi/specs/not-implemented/chatui-least-privilege-db.md
"""

import base64
import hashlib
import hmac
import os
from typing import Callable, Dict, Optional

from abi_core.common.utils import abi_logging

PREFIX = "enc:v1:"
SYSTEM_KEY_ID = "system"   # data that belongs to no user yet (waiting list)


class CryptoError(RuntimeError):
    """A value could not be encrypted or decrypted (missing or shredded key)."""


# ── KEK providers ───────────────────────────────────────────────────────

class LocalKek:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("ABI_UI_LOCAL_KEK must be 32 bytes, base64-encoded")
        self._key = key

    def wrap(self, dek: bytes) -> bytes:
        return _seal(self._key, dek)

    def unwrap(self, wrapped: bytes) -> bytes:
        return _open(self._key, wrapped)


class KmsKek:
    """Cloud KMS through its REST API (google-auth + httpx, no extra client)."""

    def __init__(self, key_name: str):
        self.key_name = key_name

    def _call(self, verb: str, field: str, value: bytes, out: str) -> bytes:
        import google.auth
        import google.auth.transport.requests
        import httpx

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloudkms"])
        credentials.refresh(google.auth.transport.requests.Request())
        resp = httpx.post(
            f"https://cloudkms.googleapis.com/v1/{self.key_name}:{verb}",
            json={field: base64.b64encode(value).decode()},
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise CryptoError(f"KMS {verb} failed: HTTP {resp.status_code}")
        return base64.b64decode(resp.json()[out])

    def wrap(self, dek: bytes) -> bytes:
        return self._call("encrypt", "plaintext", dek, "ciphertext")

    def unwrap(self, wrapped: bytes) -> bytes:
        return self._call("decrypt", "ciphertext", wrapped, "plaintext")


def kek_from_env():
    """The configured KEK, or None (encryption off)."""
    kms = os.getenv("ABI_UI_KMS_KEY", "").strip()
    if kms:
        return KmsKek(kms)
    local = os.getenv("ABI_UI_LOCAL_KEK", "").strip()
    if local:
        return LocalKek(base64.b64decode(local))
    return None


# ── AES-256-GCM ─────────────────────────────────────────────────────────

def _seal(key: bytes, plaintext: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, None)


def _open(key: bytes, sealed: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    try:
        return AESGCM(key).decrypt(sealed[:12], sealed[12:], None)
    except InvalidTag as e:
        raise CryptoError("ciphertext does not match its key") from e


# ── Data keys ───────────────────────────────────────────────────────────

class KeyRing:
    """DEKs per key id, unwrapped once and cached in this process.

    `load(key_id)` (async) returns the stored wrapped DEK or None; `store(key_id,
    wrapped)` (async) persists a new one. Both come from the data layer (the
    `data_keys` table), so this class has no database of its own."""

    def __init__(self, kek, load: Callable, store: Callable):
        self.kek = kek
        self._load, self._store = load, store
        self._cache: Dict[str, bytes] = {}

    @property
    def enabled(self) -> bool:
        return self.kek is not None

    async def dek(self, key_id: str, create: bool) -> bytes:
        if key_id in self._cache:
            return self._cache[key_id]
        wrapped = await self._load(key_id)
        if wrapped is None:
            if not create:
                raise CryptoError(f"no data key for {key_id!r} (never created, or shredded)")
            dek = os.urandom(32)
            await self._store(key_id, self.kek.wrap(dek))
            # Another writer may have stored one first: use whichever won.
            wrapped = await self._load(key_id)
            dek = self.kek.unwrap(wrapped) if wrapped is not None else dek
        else:
            dek = self.kek.unwrap(wrapped)
        self._cache[key_id] = dek
        return dek

    def forget(self, key_id: str) -> None:
        self._cache.pop(key_id, None)

    async def encrypt(self, key_id: str, value: Optional[str]) -> Optional[str]:
        if not self.enabled or value is None or is_encrypted(value):
            return value
        sealed = _seal(await self.dek(key_id, create=True), value.encode("utf-8"))
        return f"{PREFIX}{key_id}:{base64.b64encode(sealed).decode()}"

    async def decrypt(self, value):
        if not is_encrypted(value):
            return value
        key_id, _, payload = value[len(PREFIX):].partition(":")
        if not self.enabled:
            raise CryptoError("encrypted data but no key-encryption key configured")
        return _open(await self.dek(key_id, create=False), base64.b64decode(payload)).decode("utf-8")

    async def encrypt_bytes(self, key_id: str, data: bytes) -> bytes:
        """Files: raw nonce ‖ ciphertext, prefixed with a marker and the key id."""
        if not self.enabled:
            return data
        marker = f"{PREFIX}{key_id}:".encode()
        return marker + _seal(await self.dek(key_id, create=True), data)

    async def decrypt_bytes(self, data: bytes) -> bytes:
        if not data.startswith(PREFIX.encode()):
            return data
        head, _, sealed = data[len(PREFIX):].partition(b":")
        if not self.enabled:
            raise CryptoError("encrypted file but no key-encryption key configured")
        return _open(await self.dek(head.decode(), create=False), sealed)


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


# ── Identity ────────────────────────────────────────────────────────────

def identity_hash(email: str) -> str:
    """Deterministic HMAC-SHA256 of a normalized email: finds the same user
    again without storing the address. Without ABI_UI_IDENTITY_KEY (local,
    encryption off) the email itself is the identity, as before."""
    key = os.getenv("ABI_UI_IDENTITY_KEY", "").strip()
    normalized = (email or "").strip().lower()
    if not key:
        return normalized
    return "id:" + hmac.new(key.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def warn_if_disabled() -> None:
    if kek_from_env() is None:
        abi_logging("[⚠️] Chat UI data is NOT encrypted: set ABI_UI_KMS_KEY (GCP) or "
                    "ABI_UI_LOCAL_KEK (local). See chatui-least-privilege-db.md", level="warning")
