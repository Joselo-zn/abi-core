"""
Tool Card Store — Initializes and syncs tool cards with a vector store.

Mirrors the agent_card_store pattern but for ToolCards.
Reads JSON files from a directory, generates embeddings, and
upserts them into the ToolRegistry collection in Weaviate.

Usage in main.py:
    from abi_core.semantic.tool_card_store import init_tool_card_store

    tool_df = init_tool_card_store(
        tool_cards_dir="/app/tool_cards",
        embed_fn=embed_one,
        upsert_fn=upsert_tool,
        get_existing_fn=get_existing_tool_names,
    )
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from abi_core.common.utils import abi_logging


def _load_tool_cards(directory: str) -> List[Dict[str, Any]]:
    """Load all .json tool card files from a directory."""
    cards = []
    tool_dir = Path(directory)

    if not tool_dir.exists():
        abi_logging(f"[⚠️] Tool cards directory not found: {directory}")
        return cards

    for path in sorted(tool_dir.glob("*.json")):
        try:
            with open(path) as f:
                card = json.load(f)
            card["_source_path"] = str(path)
            cards.append(card)
        except (json.JSONDecodeError, OSError) as e:
            abi_logging(f"[⚠️] Skipping {path.name}: {e}")

    return cards


def init_tool_card_store(
    *,
    tool_cards_dir: str,
    embed_fn: Callable,
    upsert_fn: Callable,
    get_existing_fn: Callable,
) -> List[Dict[str, Any]]:
    """Load tool cards from disk, embed, and sync to vector store.

    Args:
        tool_cards_dir: Path to directory with .json tool card files.
        embed_fn: Function that takes a string and returns an embedding vector.
        upsert_fn: Function ``upsert_tool(tool_spec, vector)`` → uuid.
        get_existing_fn: Function that returns a set of already-stored tool names.

    Returns:
        List of loaded tool card dicts.
    """
    cards = _load_tool_cards(tool_cards_dir)

    if not cards:
        abi_logging("[⚠️] No tool cards found")
        return cards

    abi_logging(f"[🔧] Loaded {len(cards)} tool cards from {tool_cards_dir}")

    existing = set(get_existing_fn())
    abi_logging(f"[📊] {len(existing)} tool cards already in store")

    upserted = 0
    skipped = 0

    for card in cards:
        tool_name = card.get("tool_name", "")
        if not tool_name:
            continue

        if tool_name in existing:
            skipped += 1
            continue

        # Build embedding from name + description + objective + tags
        combined = ' '.join([
            tool_name,
            card.get("description", ""),
            card.get("objective", ""),
            ' '.join(card.get("edge_cases", [])),
            ' '.join(card.get("metadata", {}).get("tags", [])),
        ])

        embedding = embed_fn(combined)
        if not embedding:
            abi_logging(f"[⚠️] Failed to embed tool '{tool_name}', skipping")
            continue

        upsert_fn(card, embedding)
        upserted += 1

    if upserted:
        abi_logging(f"[📤] Upserted {upserted} new tool cards")
    if skipped:
        abi_logging(f"[⏭️] Skipped {skipped} existing tool cards")

    return cards
