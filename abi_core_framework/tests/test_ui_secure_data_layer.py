"""SecureDataLayer + schema against a real Postgres, with a least-privilege role.

Needs a disposable Postgres; skipped unless both URLs are set:
    ABI_UI_TEST_PG_OWNER_URL  postgresql+asyncpg://owner:…@host/db (creates the schema)
    ABI_UI_TEST_PG_RW_URL     same database, a role the test grants
                              USAGE + SELECT/INSERT/UPDATE only (name: abi_rw)
Spec: .abi/specs/not-implemented/chatui-least-privilege-db.md
"""

import asyncio
import base64
import json
import os
import uuid

import pytest

OWNER = os.getenv("ABI_UI_TEST_PG_OWNER_URL")
RW = os.getenv("ABI_UI_TEST_PG_RW_URL")
pytestmark = pytest.mark.skipif(not (OWNER and RW), reason="needs a disposable Postgres (see module docstring)")

SENTINEL = "SENTINEL-db-4c7"
TABLES = ["users", "threads", "steps", "feedbacks", "elements", "invites", "waiting_list", "data_keys"]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _sql(url, query, params=None):
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            res = await conn.execute(sa.text(query), params or {})
            return res.mappings().all() if res.returns_rows else res.rowcount
    finally:
        await engine.dispose()


async def _ensure_schema_as(url):
    from abi_core.ui import auth
    auth.DATABASE_URL, auth._engine, auth._schema_ready = url, None, False
    await auth._ensure_schema()


@pytest.fixture(scope="module")
def db():
    asyncio.set_event_loop(asyncio.new_event_loop())
    run(_ensure_schema_as(OWNER))
    run(_sql(OWNER, "DO $$ BEGIN CREATE ROLE abi_rw LOGIN PASSWORD 'rw'; EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
    run(_sql(OWNER, "GRANT USAGE ON SCHEMA public TO abi_rw"))
    run(_sql(OWNER, f"GRANT SELECT, INSERT, UPDATE ON {', '.join(TABLES)} TO abi_rw"))
    return True


def _layer(url=RW):
    from abi_core.ui import crypto
    from abi_core.ui.secure_data_layer import SecureDataLayer
    kek = crypto.LocalKek(base64.b64decode(os.environ["ABI_UI_LOCAL_KEK"]))
    return SecureDataLayer(conninfo=url, kek=kek)


@pytest.fixture(autouse=True)
def _kek(monkeypatch):
    os.environ.setdefault("ABI_UI_LOCAL_KEK", base64.b64encode(os.urandom(32)).decode())


def test_least_privilege_role_cannot_create_or_delete(db):
    with pytest.raises(Exception, match="permission denied"):
        run(_sql(RW, "CREATE TABLE intruder (x int)"))
    with pytest.raises(Exception, match="permission denied"):
        run(_sql(RW, "DELETE FROM threads"))


def test_schema_check_passes_without_create_when_everything_exists(db):
    run(_ensure_schema_as(RW))          # would be "permission denied" with CREATE TABLE IF NOT EXISTS


def test_missing_table_fails_with_a_clear_message(db):
    run(_sql(OWNER, "ALTER TABLE data_keys RENAME TO data_keys_aside"))
    try:
        with pytest.raises(RuntimeError, match="data_keys"):
            run(_ensure_schema_as(RW))
    finally:
        run(_sql(OWNER, "ALTER TABLE data_keys_aside RENAME TO data_keys"))


def test_a_connection_closed_by_the_server_is_replaced(db):
    """Neon closes idle connections; the pool must not hand a dead one out."""
    import sqlalchemy as sa
    from abi_core.ui import auth
    layer = _layer()
    auth.DATABASE_URL, auth._engine = RW, None

    async def auth_read():
        async with auth._get_engine().begin() as conn:
            await conn.execute(sa.text("SELECT 1"))

    for read in (lambda: layer._raw("SELECT 1 AS x", {}), auth_read):
        run(read())
        run(_sql(OWNER, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'abi_rw'"))
        run(read())                                       # "connection is closed" without pre-ping


def _conversation(layer):
    import chainlit as cl
    user = run(layer.create_user(cl.User(identifier=f"id:{uuid.uuid4().hex}", metadata={"email": f"{SENTINEL}@x.com"})))
    thread_id, step_id = str(uuid.uuid4()), str(uuid.uuid4())
    run(layer.update_thread(thread_id, name=f"titulo {SENTINEL}", user_id=user.id))
    create_step = getattr(type(layer).create_step, "__wrapped__", None)
    step = {"id": step_id, "threadId": thread_id, "name": "user", "type": "user_message",
            "input": "", "output": f"mensaje {SENTINEL}", "createdAt": "2026-10-30T00:00:00Z"}
    run(create_step(layer, step) if create_step else layer.create_step(step))
    return user, thread_id, step_id


def test_content_is_encrypted_at_rest_and_readable_through_the_layer(db):
    layer = _layer()
    user, thread_id, step_id = _conversation(layer)
    raw = run(_sql(OWNER, 'SELECT s."output", t."name", u."metadata"::text AS m FROM steps s '
                          'JOIN threads t ON t."id" = s."threadId" JOIN users u ON u."id" = t."userId" '
                          'WHERE s."id" = :id', {"id": step_id}))[0]
    assert all(SENTINEL not in (v or "") for v in raw.values())
    assert raw["output"].startswith(f"enc:v1:{user.id}:")
    thread = run(layer.get_thread(thread_id))
    assert thread["name"] == f"titulo {SENTINEL}"
    assert thread["steps"][0]["output"] == f"mensaje {SENTINEL}"
    assert run(layer.get_user(user.identifier)).metadata["email"] == f"{SENTINEL}@x.com"


def test_json_columns_come_back_parsed_on_resume(db):
    """Found 2026-10-31 in GCP: thread metadata and element props came back
    as JSON text after decryption; PlanReview resumed with empty props and
    on_chat_resume failed with "'str' object has no attribute 'get'"."""
    from abi_core.ui.secure_data_layer import SecureDataLayer
    props = {"state": "approved", "lang": "es", "view": {"steps": [f"paso {SENTINEL}"]}}
    for layer in (_layer(), SecureDataLayer(conninfo=RW, kek=None)):      # encrypted, and as without encryption
        user, thread_id, step_id = _conversation(layer)
        run(layer.update_thread(thread_id, metadata={"abi_session_token": "tok"}))
        run(layer.execute_sql('INSERT INTO elements ("id", "threadId", "forId", "name", "type", "props") '
                              'VALUES (:id, :threadId, :forId, :name, :type, :props)',
                              {"id": str(uuid.uuid4()), "threadId": thread_id, "forId": step_id, "name": "PlanReview",
                               "type": "custom", "props": json.dumps(props)}))
        thread = run(layer.get_thread(thread_id))
        assert thread["metadata"]["abi_session_token"] == "tok"
        assert thread["elements"][0]["props"] == props
        assert thread["elements"][0]["name"] == "PlanReview"
    raw = run(_sql(OWNER, 'SELECT props::text AS p FROM elements WHERE "threadId" = :t', {"t": thread_id}))
    assert raw and "approved" in raw[0]["p"]                         # the unencrypted layer wrote plaintext


def test_rows_encrypted_before_the_json_fix_still_parse(db):
    """The 3 rows already in Neon: a JSONB string holding the ciphertext."""
    layer = _layer()
    user, thread_id, _ = _conversation(layer)
    sealed = run(layer.keyring.encrypt(user.id, json.dumps({"abi_session_token": "old"})))
    run(_sql(OWNER, 'UPDATE threads SET "metadata" = CAST(:m AS jsonb) WHERE "id" = :id',
             {"m": json.dumps(sealed), "id": thread_id}))
    assert run(_layer().get_thread(thread_id))["metadata"]["abi_session_token"] == "old"


def test_search_still_works_on_decrypted_text(db):
    from chainlit.types import Pagination, ThreadFilter
    layer = _layer()
    user, thread_id, _ = _conversation(layer)
    found = run(layer.list_threads(Pagination(first=10), ThreadFilter(userId=user.id, search=SENTINEL)))
    assert [t["id"] for t in found.data] == [thread_id]


def test_soft_delete_thread_hides_it_and_keeps_the_rows(db):
    from chainlit.types import Pagination, ThreadFilter
    layer = _layer()
    user, thread_id, step_id = _conversation(layer)
    run(layer.delete_thread(thread_id))
    assert run(layer.get_thread(thread_id)) is None
    assert run(layer.list_threads(Pagination(first=10), ThreadFilter(userId=user.id))).data == []
    row = run(_sql(OWNER, 'SELECT "deletedAt", "deletedUserId" FROM threads WHERE "id" = :id', {"id": thread_id}))[0]
    assert row["deletedAt"] and row["deletedUserId"] == user.id
    assert run(_sql(OWNER, 'SELECT count(*) AS n FROM steps WHERE "threadId" = :id', {"id": thread_id}))[0]["n"] == 1


def test_feedback_soft_delete_and_vote_again(db):
    from chainlit.types import Feedback
    layer = _layer()
    _, thread_id, step_id = _conversation(layer)
    fid = run(layer.upsert_feedback(Feedback(forId=step_id, threadId=thread_id, value=1, comment=f"nota {SENTINEL}")))
    raw = run(_sql(OWNER, 'SELECT "comment" FROM feedbacks WHERE "id" = :id', {"id": fid}))[0]
    assert SENTINEL not in raw["comment"]
    run(layer.delete_feedback(fid))
    assert not run(layer.get_thread(thread_id))["steps"][0].get("feedback")
    run(layer.upsert_feedback(Feedback(id=fid, forId=step_id, threadId=thread_id, value=0)))
    assert run(layer.get_thread(thread_id))["steps"][0]["feedback"]["value"] == 0


def test_steps_and_elements_are_never_deleted(db):
    layer = _layer()
    _, thread_id, step_id = _conversation(layer)
    assert run(layer.delete_step(step_id)) is True
    assert run(_sql(OWNER, 'SELECT count(*) AS n FROM steps WHERE "id" = :id', {"id": step_id}))[0]["n"] == 1


def test_rows_from_before_encryption_still_read(db):
    layer = _layer()
    user, thread_id, _ = _conversation(layer)
    legacy = str(uuid.uuid4())
    run(_sql(OWNER, 'INSERT INTO steps ("id", "threadId", "name", "type", "output", "createdAt", "metadata") '
                    "VALUES (:id, :t, 'old', 'assistant_message', 'texto viejo', '2026-01-01', '{}')",
             {"id": legacy, "t": thread_id}))
    outputs = {s["output"] for s in run(layer.get_thread(thread_id))["steps"]}
    assert "texto viejo" in outputs


def test_shredding_a_users_key_makes_their_data_unreadable(db):
    from abi_core.ui.crypto import CryptoError
    layer = _layer()
    user, thread_id, _ = _conversation(layer)
    run(_sql(OWNER, 'UPDATE data_keys SET "shreddedAt" = now()::text WHERE "keyId" = :k', {"k": user.id}))
    fresh = _layer()                                  # no cached key
    with pytest.raises(CryptoError):
        run(fresh.get_thread(thread_id))
