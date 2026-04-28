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
        get_existing_uris_fn=get_existing_agent_card_uris,
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
    get_existing_uris_fn: Callable,
):
    """Initialize vector store and sync agent card embeddings.

    Args:
        build_embeddings_fn: Returns a DataFrame with columns
            ``card_uri``, ``agent_card`` (dict), ``card_embeddings`` (vector).
        ensure_collections_fn: Creates vector store collections if missing.
        upsert_fn: Upserts a list of item dicts to the vector store.
        get_existing_uris_fn: Returns a set/list of already-stored card URIs.

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

    existing_uris = set(get_existing_uris_fn())
    abi_logging(f"[📊] Found {len(existing_uris)} existing agent cards in store")

    items = []
    skipped = 0

    for _idx, row in df.iterrows():
        card_uri = row["card_uri"]

        if card_uri in existing_uris:
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
