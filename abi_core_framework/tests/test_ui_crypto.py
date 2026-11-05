"""abi_core.ui.crypto — envelope encryption for the Chat UI's data.

Spec: .abi/specs/not-implemented/chatui-least-privilege-db.md
"""

import asyncio
import base64
import os

import pytest

pytest.importorskip("cryptography")

from abi_core.ui import crypto  # noqa: E402

SENTINEL = "SENTINEL-chat-9f1"


def _ring(kek=None):
    store = {}

    async def load(k):
        return store.get(k)

    async def store_(k, w):
        store.setdefault(k, w)

    return crypto.KeyRing(kek or crypto.LocalKek(os.urandom(32)), load, store_), store


def run(coro):
    return asyncio.run(coro)


def test_round_trip_and_ciphertext_hides_content():
    ring, store = _ring()
    sealed = run(ring.encrypt("user-1", f"hola {SENTINEL}"))
    assert sealed.startswith("enc:v1:user-1:") and SENTINEL not in sealed
    assert run(ring.decrypt(sealed)) == f"hola {SENTINEL}"
    assert set(store) == {"user-1"}                       # one wrapped DEK per user
    assert run(ring.encrypt("user-1", "x")) != run(ring.encrypt("user-1", "x"))   # fresh nonce


def test_plaintext_from_before_encryption_is_returned_as_is():
    ring, _ = _ring()
    assert run(ring.decrypt("written before encryption")) == "written before encryption"
    assert run(ring.decrypt(None)) is None


def test_values_are_decrypted_by_their_own_key_id():
    ring, _ = _ring()
    a, b = run(ring.encrypt("user-a", "A")), run(ring.encrypt("user-b", "B"))
    ring._cache.clear()                                   # a new process: keys come from the store
    assert (run(ring.decrypt(a)), run(ring.decrypt(b))) == ("A", "B")


def test_shredded_key_makes_data_unreadable():
    ring, store = _ring()
    sealed = run(ring.encrypt("user-1", SENTINEL))
    store.pop("user-1")
    ring.forget("user-1")
    with pytest.raises(crypto.CryptoError):
        run(ring.decrypt(sealed))


def test_wrong_kek_cannot_unwrap():
    ring, store = _ring()
    sealed = run(ring.encrypt("user-1", SENTINEL))
    other = crypto.KeyRing(crypto.LocalKek(os.urandom(32)), lambda k: _get(store, k), lambda k, w: None)
    with pytest.raises(crypto.CryptoError):
        run(other.decrypt(sealed))


async def _get(store, k):
    return store.get(k)


def test_files_round_trip():
    ring, _ = _ring()
    data = os.urandom(5000) + SENTINEL.encode()
    sealed = run(ring.encrypt_bytes("user-1", data))
    assert SENTINEL.encode() not in sealed
    assert run(ring.decrypt_bytes(sealed)) == data
    assert run(ring.decrypt_bytes(b"plain file")) == b"plain file"


def test_disabled_ring_stores_plaintext_but_refuses_ciphertext():
    ring = crypto.KeyRing(None, None, None)
    assert run(ring.encrypt("u", "texto")) == "texto"
    with pytest.raises(crypto.CryptoError):
        run(ring.decrypt("enc:v1:u:AAAA"))


def test_identity_hash(monkeypatch):
    monkeypatch.setenv("ABI_UI_IDENTITY_KEY", "k1")
    h = crypto.identity_hash("Jane@Example.com ")
    assert h.startswith("id:") and "jane" not in h
    assert h == crypto.identity_hash("jane@example.com")  # normalized, deterministic
    monkeypatch.setenv("ABI_UI_IDENTITY_KEY", "k2")
    assert crypto.identity_hash("jane@example.com") != h
    monkeypatch.delenv("ABI_UI_IDENTITY_KEY")
    assert crypto.identity_hash("Jane@Example.com") == "jane@example.com"   # local, as before


def test_kek_from_env(monkeypatch):
    monkeypatch.delenv("ABI_UI_KMS_KEY", raising=False)
    monkeypatch.delenv("ABI_UI_LOCAL_KEK", raising=False)
    assert crypto.kek_from_env() is None
    monkeypatch.setenv("ABI_UI_LOCAL_KEK", base64.b64encode(os.urandom(32)).decode())
    assert isinstance(crypto.kek_from_env(), crypto.LocalKek)
    monkeypatch.setenv("ABI_UI_KMS_KEY", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
    assert isinstance(crypto.kek_from_env(), crypto.KmsKek)
    with pytest.raises(ValueError):
        crypto.LocalKek(b"short")
