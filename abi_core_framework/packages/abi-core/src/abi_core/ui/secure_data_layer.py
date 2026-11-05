"""Chainlit's SQLAlchemyDataLayer with application-level encryption and
soft deletes — for a database role with SELECT/INSERT/UPDATE only.

Every query of the base class goes through execute_sql(query, parameters)
(chainlit 2.12.0): this subclass encrypts the sensitive parameters before
running it and decrypts encrypted values in the rows it returns, so none of
Chainlit's queries is copied. The DEK is the owning user's (crypto-shredding):
resolved from the parameters (userId, or threadId → its thread's user), or
from the Chainlit session's user when the thread has no owner in the base yet.

Deletes are soft: a thread or a feedback is hidden, never removed; steps and
elements are kept (the UI does not delete them).

Spec: .abi/specs/not-implemented/chatui-least-privilege-db.md
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from chainlit.context import context_var
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from abi_core.common.utils import abi_logging
from abi_core.ui.crypto import SYSTEM_KEY_ID, KeyRing, is_encrypted

# Parameters (= columns) whose content is the user's. JSONB columns must
# stay valid JSON, so their ciphertext is stored as a JSON string.
_TEXT_COLUMNS = {"input", "output", "name", "comment"}
_JSON_COLUMNS = {"metadata", "generation", "props"}
_JSON_SUFFIXES = tuple(_JSON_COLUMNS)
_TABLE = re.compile(r'\b(?:INSERT\s+INTO|UPDATE)\s+"?(\w+)"?', re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_user_id() -> Optional[str]:
    """The persisted user of the current Chainlit session, if any."""
    ctx = context_var.get(None)
    user = getattr(getattr(ctx, "session", None), "user", None)
    return getattr(user, "id", None)


class SecureDataLayer(SQLAlchemyDataLayer):
    def __init__(self, conninfo: str, storage_provider=None, kek=None, **kwargs):
        """`kek`: crypto.kek_from_env() — None leaves encryption off (local only)."""
        # Chainlit adds the SSL context to this same dict (ssl_require).
        kwargs["connect_args"] = dict(kwargs.get("connect_args") or {})
        super().__init__(conninfo=conninfo, storage_provider=storage_provider, **kwargs)
        # Chainlit's engine has no pool_pre_ping: Neon closes idle connections
        # and the pool would hand one out ("connection is closed"). Replaced
        # before any connection is opened.
        self.engine = create_async_engine(conninfo, connect_args=kwargs["connect_args"], pool_pre_ping=True)
        self.async_session = sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)
        self.keyring = KeyRing(kek, self._load_key, self._store_key)
        if storage_provider is not None and hasattr(storage_provider, "attach"):
            storage_provider.attach(self.keyring)
        self._thread_user: Dict[str, str] = {}

    # ── data_keys (outside execute_sql: never encrypted) ────────────────

    async def _raw(self, query: str, parameters: dict):
        async with self.engine.begin() as conn:
            result = await conn.execute(text(query), parameters)
            return result.mappings().all() if result.returns_rows else result.rowcount

    async def _load_key(self, key_id: str) -> Optional[bytes]:
        rows = await self._raw('SELECT "wrapped" FROM data_keys WHERE "keyId" = :k AND "shreddedAt" IS NULL',
                               {"k": key_id})
        return bytes.fromhex(rows[0]["wrapped"]) if rows else None

    async def _store_key(self, key_id: str, wrapped: bytes) -> None:
        await self._raw('INSERT INTO data_keys ("keyId", "wrapped", "createdAt") VALUES (:k, :w, :t) '
                        'ON CONFLICT ("keyId") DO NOTHING', {"k": key_id, "w": wrapped.hex(), "t": _now()})

    # ── whose key ───────────────────────────────────────────────────────

    async def _user_of_thread(self, thread_id: str) -> Optional[str]:
        if thread_id in self._thread_user:
            return self._thread_user[thread_id]
        rows = await self._raw('SELECT COALESCE("userId", "deletedUserId") AS u FROM threads WHERE "id" = :id',
                               {"id": thread_id})
        user = rows[0]["u"] if rows else None
        if user:
            self._thread_user[thread_id] = user
        return user

    async def _key_for(self, table: str, p: dict) -> str:
        if p.get("userId"):
            return p["userId"]
        if table == "users":
            if p.get("id"):
                return p["id"]
            if p.get("identifier"):
                rows = await self._raw('SELECT "id" FROM users WHERE "identifier" = :i', {"i": p["identifier"]})
                if rows:
                    return rows[0]["id"]
        thread_id = p.get("threadId") or (p.get("id") if table == "threads" else None)
        if thread_id:
            user = await self._user_of_thread(thread_id)
            if user:
                return user
        # Chainlit writes a new thread's first message before the thread and
        # its user: the session's user owns it.
        session_user = _session_user_id()
        if session_user:
            return session_user
        # No owner known (outside a Chainlit session): the system key,
        # logged so a gap in crypto-shredding is visible.
        abi_logging(f"[🔐] No owner for a write to {table}: system key", level="warning")
        return SYSTEM_KEY_ID

    # ── the single entry point ──────────────────────────────────────────

    async def execute_sql(self, query: str, parameters: dict):
        if self.keyring.enabled and parameters:
            match = _TABLE.search(query)
            sensitive = [k for k in parameters if (k in _TEXT_COLUMNS or k in _JSON_COLUMNS)
                         and isinstance(parameters[k], str) and not is_encrypted(parameters[k])]
            if match and sensitive:
                table = match.group(1).lower()
                key_id = await self._key_for(table, parameters)
                parameters = dict(parameters)
                for k in sensitive:
                    sealed = await self.keyring.encrypt(key_id, parameters[k])
                    parameters[k] = json.dumps(sealed) if k in _JSON_COLUMNS else sealed
        result = await super().execute_sql(query=query, parameters=parameters)
        if isinstance(result, list):
            result = [await self._decrypt_row(row) for row in result]
        return result

    async def _decrypt_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        for k, v in row.items():
            if isinstance(v, str) and v.startswith('"enc:v1:'):
                v = json.loads(v)          # JSONB holding a ciphertext
            if is_encrypted(v):
                v = await self.keyring.decrypt(v)
                # A JSON column's plaintext is JSON text; Chainlit expects
                # the parsed value, as the unencrypted JSONB returns it (a
                # str here left PlanReview with empty props on resume).
                # Chainlit's aliases keep the column name at the end
                # (step_metadata, thread_metadata, props, step_generation).
                if k.endswith(_JSON_SUFFIXES) and isinstance(v, str):
                    v = json.loads(v)
            out[k] = v
        return out

    # ── soft deletes ────────────────────────────────────────────────────

    async def delete_thread(self, thread_id: str):
        # Kept, hidden: out of the user's list (userId cleared, the owner
        # moves to deletedUserId — still used for its key) and get_thread.
        await self._raw('UPDATE threads SET "deletedAt" = :t, "deletedUserId" = COALESCE("userId", "deletedUserId"), '
                        '"userId" = NULL WHERE "id" = :id', {"t": _now(), "id": thread_id})

    async def get_thread(self, thread_id: str):
        rows = await self._raw('SELECT "deletedAt" FROM threads WHERE "id" = :id', {"id": thread_id})
        if rows and rows[0]["deletedAt"]:
            return None
        return await super().get_thread(thread_id)

    async def delete_feedback(self, feedback_id: str) -> bool:
        # Kept, hidden: its forId no longer matches a step, so no thread
        # shows it; the original stays recoverable after the prefix.
        await self._raw('UPDATE feedbacks SET "deletedAt" = :t, '
                        '"forId" = CASE WHEN "forId" LIKE \'deleted:%\' THEN "forId" ELSE \'deleted:\' || "forId" END '
                        'WHERE "id" = :id', {"t": _now(), "id": feedback_id})
        return True

    async def upsert_feedback(self, feedback) -> str:
        feedback_id = await super().upsert_feedback(feedback)
        # A vote given again after being removed: visible again.
        await self._raw('UPDATE feedbacks SET "deletedAt" = NULL, "forId" = :f WHERE "id" = :id',
                        {"f": feedback.forId, "id": feedback_id})
        return feedback_id

    async def delete_step(self, step_id: str):
        abi_logging(f"[🗂️] delete_step({step_id}) ignored: deletes are soft and steps are kept")
        return True

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        abi_logging(f"[🗂️] delete_element({element_id}) ignored: deletes are soft and elements are kept")
        return True
