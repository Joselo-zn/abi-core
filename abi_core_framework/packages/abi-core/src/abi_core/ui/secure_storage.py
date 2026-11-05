"""Chainlit storage client that keeps attachments encrypted in the bucket.

Wraps chainlit's S3StorageClient:
- upload_file encrypts the content with the owner's DEK. Chainlit builds the
  object key as "<user id>/<element id>[/<file name>]"; the user id selects
  the key and the file name is dropped from the key, so it is not visible in
  the bucket either.
- get_read_url returns a Chat UI route, not a presigned bucket URL: the
  browser could not decrypt the object. The route (registered in auth.py)
  checks the session owns the object, decrypts it and streams it.
- delete_file does not delete (soft deletes): the object stays encrypted,
  unreadable once its owner's key is shredded.

Spec: .abi/specs/not-implemented/chatui-least-privilege-db.md
"""

from typing import Any, Dict, Optional, Tuple, Union

from chainlit.data.storage_clients.base import BaseStorageClient

from abi_core.common.utils import abi_logging
from abi_core.ui.crypto import SYSTEM_KEY_ID

FILES_ROUTE = "/abi-ui/files"


def split_key(object_key: str) -> Tuple[str, str]:
    """'<user>/<element>[/<name>]' -> (owner key id, stored object key)."""
    parts = object_key.strip("/").split("/")
    owner = parts[0] if parts and parts[0] not in ("", "unknown") else SYSTEM_KEY_ID
    return owner, "/".join(parts[:2])


class EncryptedStorageClient(BaseStorageClient):
    def __init__(self, inner):
        self.inner = inner          # chainlit's S3StorageClient
        self.keyring = None         # attached by SecureDataLayer

    def attach(self, keyring) -> None:
        self.keyring = keyring

    async def upload_file(self, object_key: str, data: Union[bytes, str], mime: str = "application/octet-stream",
                          overwrite: bool = True, content_disposition: Optional[str] = None) -> Dict[str, Any]:
        owner, stored_key = split_key(object_key)
        raw = data.encode("utf-8") if isinstance(data, str) else data
        sealed = await self.keyring.encrypt_bytes(owner, raw) if self.keyring else raw
        await self.inner.upload_file(object_key=stored_key, data=sealed, mime="application/octet-stream",
                                     overwrite=overwrite, content_disposition=content_disposition)
        return {"object_key": stored_key, "url": f"{FILES_ROUTE}/{stored_key}"}

    async def get_read_url(self, object_key: str) -> str:
        return f"{FILES_ROUTE}/{object_key}"

    async def delete_file(self, object_key: str) -> bool:
        abi_logging(f"[🗂️] delete_file ignored: deletes are soft (object kept, encrypted)")
        return True

    async def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if close:
            await close()

    async def read_decrypted(self, stored_key: str) -> bytes:
        """For the files route: the object's plaintext."""
        import asyncio

        def _get():
            return self.inner.client.get_object(Bucket=self.inner.bucket, Key=stored_key)["Body"].read()

        data = await asyncio.to_thread(_get)
        return await self.keyring.decrypt_bytes(data) if self.keyring else data
