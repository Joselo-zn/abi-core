# mcp_server/embeddings.py
# -*- coding: utf-8 -*-
"""
MVP Embeddings provider for ABI.

- Backend: Ollama embeddings API served by the base LLM container.
- Normalizes vectors (L2) so that dot product == cosine similarity.
- Includes small LRU cache to avoid recomputing common queries.
- Designed to be swapped later by a robust provider (TEI/Weaviate).

Env vars:
    ABI_LLM_BASE   : Base URL for Ollama (default: http://-ollama:11434)
    EMBED_MODEL  : Embedding model id in Ollama (default: nomic-embed-text)
    HTTP_TIMEOUT : Requests timeout in seconds (default: 60)

Public API:
    embed_one(text: str) -> list[float]
    embed_texts(texts: list[str]) -> list[list[float]]
    ping() -> bool            # quick health check (optional)
"""

from __future__ import annotations

import os
import time
import json

from pathlib import Path

from functools import lru_cache
from typing import List, Optional, Tuple

import requests
import numpy as np
import pandas as pd

from abi_core.common.utils import abi_logging

# ----------------------------
# Configuration
# ----------------------------
ABI_LLM_BASE  = os.getenv("ABI_LLM_BASE", "http://testproject-ollama:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "60"))

_EMBED_URL = f"{ABI_LLM_BASE}/api/embeddings"
_TAGS_URL  = f"{ABI_LLM_BASE}/api/tags"
_agent_cards_df_cache: Optional[pd.DataFrame] = None

# ----------------------------
# Internal helpers
# ----------------------------
def _normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize vector to ensure dot == cosine."""
    n = float(np.linalg.norm(vec))
    if n == 0.0 or not np.isfinite(n):
        return vec  # return as-is; caller may handle empty/invalid vectors
    return vec / n

def load_agent_cards() -> Tuple[List[str], List[dict]]:
    """Retrieves all Agent Cards stored as JSON files in the configured directory.
    
    Returns:
        tuple:
            - card_uris (List[str]): List of file paths for each Agent Card JSON.
            - agent_cards (List[dict]): List of parsed JSON dictionaries representing Agent Cards.
    
    Behavior:
        - Skips unreadable or malformed JSON files with a warning.
        - Returns empty lists if no Agent Cards are found.
    """
    AGENT_CARDS_DIR = os.getenv("AGENT_CARDS_BASE", "/app/agent_cards")
    dir_path = Path(AGENT_CARDS_DIR)

    if not dir_path.is_dir():
        abi_logging(f"❌ Agent Cards directory not found or is not a directory: {AGENT_CARDS_DIR}")
        return [], []

    card_uris = []
    agent_cards = []

    for file_path in dir_path.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                card_data = json.load(f)
                card_uris.append(str(file_path))
                agent_cards.append(card_data)
        except json.JSONDecodeError:
            abi_logging(f"⚠️ Invalid JSON format in file: {file_path}")
        except Exception as e:
            abi_logging(f"❌ Error reading {file_path}: {e}")

    return card_uris, agent_cards

def build_agent_card_embeddings(force_reload: bool = False) -> Optional[pd.DataFrame]:
    """Generates embeddings for all available Agent Cards using multi-field strategy.
    
    Multi-field embedding combines:
    - Agent name
    - Agent description
    - Supported tasks
    - Skills descriptions
    
    This provides richer semantic matching compared to single-field embeddings.
    
    Args:
        force_reload (bool, optional): If True, forces regeneration of embeddings 
                                       even if cached data exists. Defaults to False.
    
    Returns:
        pd.DataFrame | None:
            - DataFrame with columns:
                - card_uri: Path to the JSON file for the Agent Card.
                - agent_card: Original JSON dictionary of the Agent Card.
                - card_embeddings: Vector embedding of the combined Agent Card fields.
                - combined_text: The text used for embedding generation.
            - None if no Agent Cards are found.
    
    Note:
        This is the MVP version — embeddings are computed locally via `embed_one()`.
        In the robust version, these embeddings will be persisted in Weaviate for semantic search.
    """
    global _agent_cards_df_cache

    if _agent_cards_df_cache is not None and not force_reload:
        return _agent_cards_df_cache

    card_uris, agent_cards = load_agent_cards()

    if not agent_cards:
        abi_logging("⚠️ No Agent Cards found. Cannot generate embeddings.")
        return None
    try:
        df = pd.DataFrame({
            'card_uri': card_uris,
            'agent_card': agent_cards
        })
        
        # Multi-field embedding strategy (default)
        def create_combined_text(card: dict) -> str:
            """Combine multiple fields for richer embedding."""
            parts = [
                card.get('name', ''),
                card.get('description', ''),
                ' '.join(card.get('supportedTasks', [])),
                ' '.join([
                    skill.get('description', '') 
                    for skill in card.get('skills', [])
                ])
            ]
            return ' '.join(filter(None, parts))
        
        df['combined_text'] = df['agent_card'].apply(create_combined_text)
        df['card_embeddings'] = df['combined_text'].apply(embed_one)

        _agent_cards_df_cache = df
        abi_logging(f"✅ Generated embeddings for {len(df)} agent cards using multi-field strategy")
        return df

    except Exception as e:
        abi_logging(f"❌ Unexpected error while generating embeddings: {e}")
        return None

def _post_json(url: str, payload: dict, timeout: float) -> dict:
    """POST JSON with basic error handling and logging."""
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        abi_logging(f"❌ [embeddings] HTTP error calling {url}: {e}")
        raise
    except ValueError as e:
        abi_logging(f"❌ [embeddings] Invalid JSON response from {url}: {e}")
        raise


def _has_model(model: str) -> bool:
    """Check if model appears in Ollama /api/tags (best-effort)."""
    try:
        r = requests.get(_TAGS_URL, timeout=min(HTTP_TIMEOUT, 10))
        r.raise_for_status()
        return model in r.text
    except requests.RequestException:
        return False


# ----------------------------
# Public: health check
# ----------------------------
def ping() -> bool:
    """Quick check: Ollama reachable and likely alive."""
    try:
        r = requests.get(_TAGS_URL, timeout=min(HTTP_TIMEOUT, 5))
        r.raise_for_status()
        return True
    except requests.RequestException:
        return False

# ----------------------------
# Public: embeddings (cached)
# ----------------------------
@lru_cache(maxsize=1024)
def _embed_one_cached(text: str) -> tuple[float, ...]:
    """Core call to Ollama with small retry & LRU cache.

    Returns a tuple (hashable) so lru_cache can store it.
    Caller-facing embed_one() converts it back to list[float].
    """
    # Quick sanity check to fail fast with a clear log if model is missing.
    if not _has_model(EMBED_MODEL):
        abi_logging(f"⚠️ [embeddings] Model '{EMBED_MODEL}' not listed in /api/tags at {ABI_LLM_BASE}. "
                       f"Ensure it was pulled and is available.")

    backoff = 1.0
    last_exc = None
    for attempt in range(1, 4):  # up to 3 attempts
        try:
            payload = {"model": EMBED_MODEL, "prompt": text}
            data = _post_json(_EMBED_URL, payload, timeout=HTTP_TIMEOUT)

            raw = data.get("embedding")
            if raw is None:
                raise RuntimeError(f"Missing 'embedding' in response: {json.dumps(data)[:200]}")

            vec = np.array(raw, dtype=float)
            vec = _normalize(vec)
            return tuple(float(x) for x in vec.tolist())

        except Exception as e:  # noqa: BLE001 - we log and retry bounded attempts
            last_exc = e
            abi_logging(f"⚠️ [embeddings] attempt {attempt}/3 failed: {e}")
            time.sleep(backoff)
            backoff *= 2

    # If we reach here, all attempts failed
    abi_logging("❌ [embeddings] All attempts to get embedding failed")
    # Return empty tuple to signal failure to callers that check length/size
    return tuple()


def embed_one(text: str, persist: bool = False, *, uri: str | None = None, item_id: str | None = None, metadata: dict | None = None) -> List[float]:
    """Generate a single embedding for `text` using the local Ollama service.

    New: optional persistence to vector DB (weaviate) via upsert_agent_cards().
    Args:
        text (str): Input text to embed.
        persist (bool): If True, try to store the resulting vector in the vector DB.
        uri (str|None): optional uri to store with the item.
        item_id (str|None): optional id (UUID) for the item.
        metadata (dict|None): optional metadata to persist.

    Returns:
        list[float]: Normalized embedding vector, or [] on failure.
    """
    vec_t = _embed_one_cached(text)
    if not vec_t:
        return []

    vec = list(vec_t)

    if persist:
        try:
            # lazy import to avoid extra deps/circular imports at module import time
            from .weaviate_store import ensure_collections, upsert_agent_cards
            ensure_collections()
            item = {
                "id": item_id,
                "text": text,
                "uri": uri,
                "metadata": metadata or {},
                "vector": vec,
                "origin": "agent_card"
            }
            # upsert_agent_cards expects an iterable of dicts
            upsert_agent_cards([item])
        except Exception as e:
            abi_logging(f"⚠️ [embeddings] persist to vector DB failed: {e}")

    return vec


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts.

    Note:
        - Ollama's embeddings API is one-by-one. For MVP we call `embed_one`
          per text. The LRU cache mitigates repeated inputs.
        - Returns a list of vectors (may contain [] for failed items).

    Args:
        texts (list[str]): Input texts.

    Returns:
        list[list[float]]: List of normalized embeddings (possibly empty vectors on failure).
    """
    return [embed_one(t) for t in texts]


def get_embed_model_name() -> str:
    """Nombre del modelo de embeddings activo (para logging/diagnóstico)."""
    return EMBED_MODEL

def clear_caches() -> None:
    """Limpia caches internas de embeddings y el DF en memoria."""
    global _agent_cards_df_cache
    _agent_cards_df_cache = None
    try:
        _embed_one_cached.cache_clear()  # limpia LRU
    except Exception:
        # por si cambiaron la ref en runtime; ser tolerante
        pass