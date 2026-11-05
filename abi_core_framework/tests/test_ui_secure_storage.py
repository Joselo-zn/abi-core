"""EncryptedStorageClient: attachments encrypted in the bucket, served by a
Chat UI route. Spec: .abi/specs/not-implemented/chatui-least-privilege-db.md
"""

import asyncio
import os
from types import SimpleNamespace

import pytest

pytest.importorskip("chainlit")
pytest.importorskip("cryptography")

from abi_core.ui import crypto  # noqa: E402
from abi_core.ui.secure_storage import FILES_ROUTE, EncryptedStorageClient, split_key  # noqa: E402

SENTINEL = b"SENTINEL-file-2b8"


class _FakeS3:
    """Stands in for chainlit's S3StorageClient (bucket + boto3 client)."""

    def __init__(self):
        self.bucket, self.objects = "b", {}
        self.client = SimpleNamespace(get_object=lambda Bucket, Key: {"Body": SimpleNamespace(read=lambda: self.objects[Key])})

    async def upload_file(self, object_key, data, mime="application/octet-stream", overwrite=True, content_disposition=None):
        self.objects[object_key] = data
        return {"object_key": object_key, "url": f"https://bucket/{object_key}"}

    async def delete_file(self, object_key):
        raise AssertionError("must not delete")


def _client():
    store = {}

    async def load(k):
        return store.get(k)

    async def save(k, w):
        store.setdefault(k, w)

    inner, client = _FakeS3(), None
    client = EncryptedStorageClient(inner)
    client.attach(crypto.KeyRing(crypto.LocalKek(os.urandom(32)), load, save))
    return client, inner


def run(coro):
    return asyncio.run(coro)


def test_split_key_drops_the_file_name_and_finds_the_owner():
    assert split_key("user-1/el-9/report final.pdf") == ("user-1", "user-1/el-9")
    assert split_key("unknown/el-9") == (crypto.SYSTEM_KEY_ID, "unknown/el-9")


def test_upload_encrypts_and_read_decrypts():
    client, inner = _client()
    data = b"%PDF-1.7 " + SENTINEL + os.urandom(200)
    out = run(client.upload_file("user-1/el-9/report.pdf", data, mime="application/pdf"))
    assert out == {"object_key": "user-1/el-9", "url": f"{FILES_ROUTE}/user-1/el-9"}
    assert list(inner.objects) == ["user-1/el-9"]                 # no file name in the bucket
    assert SENTINEL not in inner.objects["user-1/el-9"]           # encrypted at rest
    assert run(client.read_decrypted("user-1/el-9")) == data


def test_read_url_is_the_chat_ui_route_and_delete_keeps_the_object():
    client, inner = _client()
    run(client.upload_file("user-1/el-9", b"x"))
    assert run(client.get_read_url("user-1/el-9")) == f"{FILES_ROUTE}/user-1/el-9"
    assert run(client.delete_file("user-1/el-9")) is True
    assert "user-1/el-9" in inner.objects
