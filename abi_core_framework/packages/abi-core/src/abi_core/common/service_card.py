"""
ServiceCard — Identity card for non-agent services.

Services (webapp, semantic layer, guardian) need to authenticate against
MCP servers but don't have AgentCards. A ServiceCard provides the same
HMAC-based identity without requiring A2A capabilities or skills.

Usage:
    card = ServiceCard.from_file("service_cards/webapp.json")
    context = card.build_context(tool_name="find_agent", query="planner")

    # Or with MCPToolkit:
    toolkit = MCPToolkit(service_card=card)
    result = await toolkit.find_agent(query="planner")
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class ServiceCard:
    """Identity card for a non-agent service.

    Attributes:
        service_id: Unique identifier (e.g. "service://webapp").
        name: Human-readable name.
        description: What the service does.
        service_type: Category — "webapp", "semantic_layer", "guardian", etc.
        url: Service endpoint URL.
        version: Semantic version.
        auth: HMAC auth config with method, key_id, shared_secret.
        actions: What MCP actions this service can execute (identity, not authorization).
        checksum: SHA-256 hash for integrity verification.
        install_key: Unique install identifier (service://name@version).
        origin: Server/node this service comes from.
        metadata: Arbitrary key-value pairs.
    """

    service_id: str
    name: str
    description: str = ""
    service_type: str = "service"
    url: str = ""
    version: str = "1.0.0"
    auth: Dict[str, str] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)
    checksum: str = ""
    install_key: str = ""
    origin: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.install_key:
            self.install_key = f"service://{self.name}@{self.version}"

    # ── Context building (replaces build_semantic_context_from_card) ──

    def build_context(
        self,
        tool_name: str,
        query: str = "",
        mcp_method: str = "callTool",
        user_email: str = None,
    ) -> Dict[str, Any]:
        """Build authenticated context for MCP calls.

        Produces the same structure as ``build_semantic_context_from_card``
        so the semantic layer validates it identically.
        """
        import base64
        import hmac as hmac_mod

        shared_secret = self.auth.get("shared_secret", "")
        key_id = self.auth.get("key_id", self.service_id)

        payload = {
            "agent_id": self.service_id,
            "tool": tool_name,
            "query": query,
            "ts": int(time.time()),
            "nonce": uuid4().hex,
        }
        if user_email:
            payload["user_email"] = user_email

        # HMAC signature (same algorithm as agent_auth.sign_payload_hmac)
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        sig = hmac_mod.new(shared_secret.encode(), body, hashlib.sha256).digest()
        signature = base64.b64encode(sig).decode()

        headers = {
            "X-ABI-Agent-ID": self.service_id,
            "X-ABI-Key-Id": key_id,
            "X-ABI-Signature": signature,
            "X-ABI-Timestamp": str(payload["ts"]),
            "X-ABI-Nonce": payload["nonce"],
        }
        if user_email:
            headers["X-ABI-User-Email"] = user_email

        ctx = {
            "agent_id": self.service_id,
            "headers": {
                "X-Agent-ID": self.service_id,
                "User-Agent": f"ABI-Service/{self.name}/1.0",
                **headers,
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool_name": tool_name,
            "mcp_method": mcp_method,
            "payload": payload,
        }
        if user_email:
            ctx["user_email"] = user_email

        return ctx

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "description": self.description,
            "service_type": self.service_type,
            "url": self.url,
            "version": self.version,
            "auth": self.auth,
            "actions": self.actions,
            "checksum": self.checksum,
            "install_key": self.install_key,
            "origin": self.origin,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceCard":
        return cls(
            service_id=data.get("service_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            service_type=data.get("service_type", "service"),
            url=data.get("url", ""),
            version=data.get("version", "1.0.0"),
            auth=data.get("auth", {}),
            actions=data.get("actions", []),
            checksum=data.get("checksum", ""),
            install_key=data.get("install_key", ""),
            origin=data.get("origin", ""),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_file(cls, path: str) -> "ServiceCard":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def __repr__(self) -> str:
        return (
            f"ServiceCard(id={self.service_id!r}, name={self.name!r}, "
            f"type={self.service_type!r}, origin={self.origin!r})"
        )

    # ── Integrity ───────────────────────────────────────────────

    @staticmethod
    def compute_checksum(code: bytes) -> str:
        """Compute SHA-256 checksum for service code."""
        return f"sha256:{hashlib.sha256(code).hexdigest()}"

    def verify_checksum(self, code: bytes) -> bool:
        """Verify service code matches the declared checksum."""
        if not self.checksum:
            return True
        return self.checksum == self.compute_checksum(code)
