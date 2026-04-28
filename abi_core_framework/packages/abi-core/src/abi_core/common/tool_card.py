"""
ToolCard — Structured metadata for MCP tools with access scope and governance.

Similar to AgentCards but for tools. Declares what resources a tool
accesses, enabling the planner to match tools against agent permissions
and the guardian to validate checksums before execution.

Usage:
    card = ToolCard.from_dict(json_data)
    card = ToolCard.from_file("tool_cards/query_sales_db.json")

    if card.can_access_table("sales_db.orders"):
        ...

    if card.verify_checksum(code_bytes):
        ...
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AccessScope:
    """Declares what resources a tool can access.

    Used by the planner to match tools against agent permissions
    and by the guardian to enforce access policies.
    """

    databases: List[str] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)  # read, write, delete, admin
    apis: List[str] = field(default_factory=list)
    storage: List[str] = field(default_factory=list)  # s3://, gs://, az://
    filesystems: List[str] = field(default_factory=list)  # local paths
    secrets: List[str] = field(default_factory=list)  # env var names

    def to_dict(self) -> Dict[str, Any]:
        return {
            "databases": self.databases,
            "tables": self.tables,
            "permissions": self.permissions,
            "apis": self.apis,
            "storage": self.storage,
            "filesystems": self.filesystems,
            "secrets": self.secrets,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccessScope":
        return cls(
            databases=data.get("databases", []),
            tables=data.get("tables", []),
            permissions=data.get("permissions", []),
            apis=data.get("apis", []),
            storage=data.get("storage", []),
            filesystems=data.get("filesystems", []),
            secrets=data.get("secrets", []),
        )


@dataclass
class ToolCard:
    """Structured metadata for an MCP tool.

    Attributes:
        tool_name: Unique identifier.
        version: Semantic version.
        description: Human-readable description.
        objective: What the tool achieves.
        parameters: Input parameter schema.
        constraints: Usage limitations.
        edge_cases: Known edge cases and expected behavior.
        implementation_hints: Technical notes for the builder.
        access_scope: Resources the tool accesses.
        checksum: SHA-256 hash of the tool's code for integrity.
        install_key: Unique install identifier (tool://name@version).
        auth: Authentication config (method, key_id).
        origin: Who created it (builder, manual, etc.).
        ephemeral: Whether the tool is temporary.
        mcp_endpoint: Where the tool is served.
        metadata: Arbitrary key-value pairs.
    """

    tool_name: str
    version: str = "1.0.0"
    description: str = ""
    objective: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: str = ""
    edge_cases: List[str] = field(default_factory=list)
    implementation_hints: str = ""
    access_scope: AccessScope = field(default_factory=AccessScope)
    checksum: str = ""
    install_key: str = ""
    auth: Dict[str, str] = field(default_factory=dict)
    origin: str = "manual"
    ephemeral: bool = False
    mcp_endpoint: str = "semantic-layer"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.install_key:
            self.install_key = f"tool://{self.tool_name}@{self.version}"

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "version": self.version,
            "description": self.description,
            "objective": self.objective,
            "parameters": self.parameters,
            "constraints": self.constraints,
            "edge_cases": self.edge_cases,
            "implementation_hints": self.implementation_hints,
            "access_scope": self.access_scope.to_dict(),
            "checksum": self.checksum,
            "install_key": self.install_key,
            "auth": self.auth,
            "origin": self.origin,
            "ephemeral": self.ephemeral,
            "mcp_endpoint": self.mcp_endpoint,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCard":
        scope_data = data.get("access_scope", {})
        scope = AccessScope.from_dict(scope_data) if isinstance(scope_data, dict) else AccessScope()

        return cls(
            tool_name=data.get("tool_name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            objective=data.get("objective", ""),
            parameters=data.get("parameters", {}),
            constraints=data.get("constraints", ""),
            edge_cases=data.get("edge_cases", []),
            implementation_hints=data.get("implementation_hints", ""),
            access_scope=scope,
            checksum=data.get("checksum", ""),
            install_key=data.get("install_key", ""),
            auth=data.get("auth", {}),
            origin=data.get("origin", "manual"),
            ephemeral=data.get("ephemeral", False),
            mcp_endpoint=data.get("mcp_endpoint", "semantic-layer"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_file(cls, path: str) -> "ToolCard":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    # ── Access checks ───────────────────────────────────────────

    def can_access_table(self, table: str) -> bool:
        """Check if this tool declares access to a specific table."""
        return table in self.access_scope.tables

    def can_access_database(self, db: str) -> bool:
        return db in self.access_scope.databases

    def can_access_storage(self, uri: str) -> bool:
        """Check if a storage URI matches any declared pattern."""
        for pattern in self.access_scope.storage:
            if pattern.endswith("*"):
                if uri.startswith(pattern[:-1]):
                    return True
            elif uri == pattern:
                return True
        return False

    def has_permission(self, perm: str) -> bool:
        return perm in self.access_scope.permissions

    def required_secrets(self) -> List[str]:
        return self.access_scope.secrets

    # ── Integrity ───────────────────────────────────────────────

    @staticmethod
    def compute_checksum(code: bytes) -> str:
        """Compute SHA-256 checksum for tool code."""
        return f"sha256:{hashlib.sha256(code).hexdigest()}"

    def verify_checksum(self, code: bytes) -> bool:
        """Verify tool code matches the declared checksum."""
        if not self.checksum:
            return True  # No checksum declared — skip
        return self.checksum == self.compute_checksum(code)

    def __repr__(self) -> str:
        scope = self.access_scope
        resources = len(scope.databases) + len(scope.tables) + len(scope.apis) + len(scope.storage)
        return (
            f"ToolCard(name={self.tool_name!r}, v={self.version}, "
            f"resources={resources}, perms={scope.permissions})"
        )
