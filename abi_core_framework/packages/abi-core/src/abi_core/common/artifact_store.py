"""
ArtifactStore — Object storage abstraction for ABI artifacts.

Provides a unified interface over S3-compatible storage (MinIO local,
AWS S3, GCS via S3 compatibility). Any component that needs to store
or retrieve files (builder, zombie, orchestrator) uses this.

Key convention: {task_id}/{filename}
    e.g. task_1_1711648000/main.py
         task_1_1711648000/config.json

Usage:
    store = ArtifactStore(
        endpoint="http://minio:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
    )
    await store.ensure_bucket()
    url = await store.upload("task_1/main.py", code_bytes)
    data = await store.download("task_1/main.py")
"""

import os
from typing import Any, Dict, List, Optional

from abi_core.common.utils import abi_logging


class ArtifactStore:
    """S3-compatible object storage client for ABI artifacts."""

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket: str = "abi-artifacts",
        region: str = "us-east-1",
    ):
        self.endpoint = endpoint or os.getenv("ARTIFACT_ENDPOINT", "http://minio:9000")
        self.access_key = access_key or os.getenv("ARTIFACT_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("ARTIFACT_SECRET_KEY", "minioadmin")
        self.bucket = bucket or os.getenv("ARTIFACT_BUCKET", "abi-artifacts")
        self.region = region
        self._client = None

    def _get_client(self):
        """Lazy-init boto3 S3 client."""
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    async def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        import asyncio

        client = self._get_client()
        try:
            await asyncio.to_thread(client.head_bucket, Bucket=self.bucket)
            abi_logging(f"[📦] Bucket '{self.bucket}' exists")
        except Exception:
            try:
                await asyncio.to_thread(
                    client.create_bucket, Bucket=self.bucket
                )
                abi_logging(f"[📦] Bucket '{self.bucket}' created")
            except Exception as e:
                abi_logging(f"[❌] Failed to create bucket '{self.bucket}': {e}")
                raise

    async def upload(
        self, key: str, content: bytes, metadata: Dict[str, str] = None
    ) -> str:
        """Upload bytes to storage. Returns the object URL."""
        import asyncio

        client = self._get_client()
        extra = {}
        if metadata:
            extra["Metadata"] = {k: str(v) for k, v in metadata.items()}

        await asyncio.to_thread(
            client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=content,
            **extra,
        )
        url = f"{self.endpoint}/{self.bucket}/{key}"
        abi_logging(f"[⬆️] Uploaded: {key} ({len(content)} bytes)")
        return url

    async def upload_file(
        self, key: str, local_path: str, metadata: Dict[str, str] = None
    ) -> str:
        """Upload a local file to storage. Returns the object URL."""
        with open(local_path, "rb") as f:
            content = f.read()
        return await self.upload(key, content, metadata)

    async def download(self, key: str) -> bytes:
        """Download an artifact as bytes."""
        import asyncio

        client = self._get_client()
        response = await asyncio.to_thread(
            client.get_object, Bucket=self.bucket, Key=key
        )
        data = response["Body"].read()
        abi_logging(f"[⬇️] Downloaded: {key} ({len(data)} bytes)")
        return data

    async def download_file(self, key: str, local_path: str) -> str:
        """Download an artifact to a local file. Returns the local path."""
        import asyncio

        client = self._get_client()
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        await asyncio.to_thread(
            client.download_file, self.bucket, key, local_path
        )
        abi_logging(f"[⬇️] Downloaded: {key} → {local_path}")
        return local_path

    async def list_artifacts(self, prefix: str = "") -> List[str]:
        """List artifact keys by prefix."""
        import asyncio

        client = self._get_client()
        response = await asyncio.to_thread(
            client.list_objects_v2, Bucket=self.bucket, Prefix=prefix
        )
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        abi_logging(f"[📋] Listed {len(keys)} artifacts with prefix '{prefix}'")
        return keys

    async def delete(self, key: str) -> bool:
        """Delete an artifact. Returns True on success."""
        import asyncio

        client = self._get_client()
        try:
            await asyncio.to_thread(
                client.delete_object, Bucket=self.bucket, Key=key
            )
            abi_logging(f"[🗑️] Deleted: {key}")
            return True
        except Exception as e:
            abi_logging(f"[❌] Failed to delete {key}: {e}")
            return False

    async def get_url(self, key: str, expires: int = 3600) -> str:
        """Generate a pre-signed URL for temporary access."""
        import asyncio

        client = self._get_client()
        url = await asyncio.to_thread(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )
        return url

    async def exists(self, key: str) -> bool:
        """Check if an artifact exists."""
        import asyncio

        client = self._get_client()
        try:
            await asyncio.to_thread(
                client.head_object, Bucket=self.bucket, Key=key
            )
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"ArtifactStore(endpoint={self.endpoint!r}, bucket={self.bucket!r})"


async def upload_workspace_artifacts(
    agent_name: str,
    workspace: str = "/app/workspace",
    exclude: Optional[List[str]] = None,
    bucket: str = None,
) -> List[Dict[str, str]]:
    """Upload new files from workspace to MinIO.

    Skips files that were downloaded as input artifacts (exclude list).
    Reusable by any agent that generates files.

    Args:
        agent_name: Agent identifier for the storage key prefix.
        workspace: Local directory to scan for files.
        exclude: List of local paths to skip (e.g. downloaded artifacts).
        bucket: Override bucket (default: from env ARTIFACT_BUCKET).

    Returns:
        List of dicts with filename, key, url, agent for each uploaded file.
    """
    if not os.path.exists(workspace):
        return []

    exclude_set = set(exclude or [])
    store = ArtifactStore(bucket=bucket)
    uploaded = []

    try:
        await store.ensure_bucket()

        for filename in os.listdir(workspace):
            filepath = os.path.join(workspace, filename)
            if not os.path.isfile(filepath) or filepath in exclude_set:
                continue
            key = f"{agent_name}/{filename}"
            url = await store.upload_file(key, filepath, metadata={
                "agent": agent_name,
                "origin": "workspace",
            })
            uploaded.append({"filename": filename, "key": key, "url": url, "agent": agent_name})
            abi_logging(f"[📤] Uploaded: {filename}")
    except Exception as e:
        abi_logging(f"[⚠️] Artifact upload failed: {e}")

    return uploaded


async def generate_download_urls(
    artifacts: List[Dict[str, str]],
    expires: int = 3600,
    bucket: str = None,
) -> List[Dict[str, str]]:
    """Generate pre-signed download URLs for a list of artifacts.

    Mutates each artifact dict in-place by adding a 'download_url' key.
    Reusable by any agent that needs to provide download links.

    Args:
        artifacts: List of dicts with at least 'key' or 'agent'+'filename'.
        expires: URL expiration in seconds (default 1 hour).
        bucket: Override bucket (default: from env ARTIFACT_BUCKET).

    Returns:
        The same list with 'download_url' added to each artifact.
    """
    if not artifacts:
        return artifacts

    try:
        store = ArtifactStore(bucket=bucket)
        for art in artifacts:
            key = art.get("key") or f"{art.get('agent', 'unknown')}/{art.get('filename', '')}"
            art["download_url"] = await store.get_url(key, expires=expires)
        abi_logging(f"[📎] Generated download URLs for {len(artifacts)} artifact(s)")
    except Exception as e:
        abi_logging(f"[⚠️] Could not generate download URLs: {e}")

    return artifacts


def format_artifact_links(artifacts: List[Dict[str, str]]) -> str:
    """Format artifacts as markdown download links.

    Args:
        artifacts: List of dicts with 'filename' and 'download_url' (or 'url').

    Returns:
        Markdown string with links, or empty string if no artifacts.
    """
    if not artifacts:
        return ""

    lines = ["\n\n📎 **Generated files:**"]
    for art in artifacts:
        fname = art.get("filename", "unknown")
        url = art.get("download_url", art.get("url", ""))
        lines.append(f"- [{fname}]({url})")

    return "\n".join(lines) + "\n"
