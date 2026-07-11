"""
Agent Card Store — Initializes and syncs agent cards with a vector store.

Encapsulates the Weaviate initialization + embedding + upsert logic
that was previously inlined in the semantic layer's server.py.

Usage in server.py:
    from abi_core.semantic.agent_card_store import init_agent_card_store

    df = init_agent_card_store(
        build_embeddings_fn=build_agent_card_embeddings,
        ensure_collections_fn=ensure_collections,
        upsert_fn=upsert_agent_cards,
        get_valid_uris_fn=get_valid_agent_card_uris,
    )
"""

import json
import uuid
from typing import Any, Callable, List, Optional, Set

from abi_core.common.utils import abi_logging


def init_agent_card_store(
    *,
    build_embeddings_fn: Callable,
    ensure_collections_fn: Callable,
    upsert_fn: Callable,
    get_valid_uris_fn: Callable,
):
    """Initialize vector store and sync agent card embeddings.

    Idempotency contract (important):
        A card is skipped ONLY if it already exists in the store **and is valid**
        (i.e. has a usable, non-empty vector). ``get_valid_uris_fn`` MUST return
        only the URIs of objects that are usable for vector search — objects that
        exist but lack a vector must NOT be reported here, so that this function
        re-upserts them (self-healing) instead of leaving them broken forever.

        Reporting existence alone (regardless of validity) reintroduces the
        integrity bug documented in ``.abi/specs/semantic-store-integrity.md``,
        where objects inserted without a vector are skipped on every startup and
        never repaired.

    Args:
        build_embeddings_fn: Returns a DataFrame with columns
            ``card_uri``, ``agent_card`` (dict), ``card_embeddings`` (vector).
        ensure_collections_fn: Creates vector store collections if missing.
        upsert_fn: Upserts a list of item dicts to the vector store.
        get_valid_uris_fn: Returns a set/list of URIs for cards already stored
            **with a valid vector**. Objects without a vector must be excluded.

    Returns:
        The DataFrame returned by *build_embeddings_fn* (or None).
    """
    abi_logging("[🗄️] Ensuring vector store collections exist...")
    ensure_collections_fn()
    abi_logging("[✅] Vector store collections ready")

    df = build_embeddings_fn()

    if df is None or df.empty:
        abi_logging("[⚠️] No agent cards found")
        return df

    valid_uris = set(get_valid_uris_fn())
    abi_logging(f"[📊] Found {len(valid_uris)} valid agent cards in store")

    items = []
    skipped = 0

    for _idx, row in df.iterrows():
        card_uri = row["card_uri"]

        # Skip only if already stored AND valid (has a vector). Invalid/missing
        # objects fall through and get re-upserted below (self-healing).
        if card_uri in valid_uris:
            skipped += 1
            continue

        agent_card = row["agent_card"]
        card_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, card_uri))

        items.append({
            "id": card_uuid,
            "text": json.dumps(agent_card),
            "uri": card_uri,
            "metadata": {
                "name": agent_card.get("name", ""),
                "description": agent_card.get("description", ""),
                "supportedTasks": agent_card.get("supportedTasks", []),
            },
            "vector": row["card_embeddings"],
            "origin": "agent_card",
        })

    if items:
        abi_logging(f"[📤] Upserting {len(items)} new agent cards...")
        upsert_fn(items)
        abi_logging(f"[✅] Successfully upserted {len(items)} agent cards")

    if skipped:
        abi_logging(f"[⏭️] Skipped {skipped} existing agent cards")

    if not items and not skipped:
        abi_logging("[⚠️] No agent cards to upsert")

    return df
