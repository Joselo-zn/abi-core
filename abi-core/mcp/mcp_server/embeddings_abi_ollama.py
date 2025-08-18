# mcp_server/embeddings.py
# -*- coding: utf-8 -*-
"""
MVP Embeddings provider for ABI.

- Backend: Ollama embeddings API served by the base LLM container.
- Normalizes vectors (L2) so that dot product == cosine similarity.
- Includes small LRU cache to avoid recomputing common queries.
- Designed to be swapped later by a robust provider (TEI/Weaviate).

Env vars:
    ABI_LLM_BASE   : Base URL for Ollama (default: http://abi-llm-base:11434)
    EMBED_MODEL  : Embedding model id in Ollama (default: nomic-embed-text)
    HTTP_TIMEOUT : Requests timeout in seconds (default: 60)

Public API:
    embed_one(text: str) -> list[float]
    embed_batch(texts: list[str]) -> list[list[float]]
    ping() -> bool            # quick health check (optional)
"""

from __future__ import annotations

import os
import time
import json
import logging
from functools import lru_cache
from typing import List

import requests
import numpy as np

logger = logging.getLogger(__name__)

# ----------------------------
# Configuration
# ----------------------------
ABI_LLM_BASE = os.getenv('ABI_LLM_BASE', 'https://abi_llmbase:8000')
ABI_LLM_BASE  = os.getenv("ABI_LLM_BASE", "http://abi-llm-base:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "jina/jina-embeddings-v2-base-es")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "60"))

_EMBED_URL = f"{ABI_LLM_BASE}/api/embeddings"
_TAGS_URL  = f"{ABI_LLM_BASE}/api/tags"


# ----------------------------
# Internal helpers
# ----------------------------
def _normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize vector to ensure dot == cosine."""
    n = float(np.linalg.norm(vec))
    if n == 0.0 or not np.isfinite(n):
        return vec  # return as-is; caller may handle empty/invalid vectors
    return vec / n


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    """POST JSON with basic error handling and logging."""
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"[embeddings] HTTP error calling {url}: {e}", exc_info=True)
        raise
    except ValueError as e:
        logger.error(f"[embeddings] Invalid JSON response from {url}: {e}", exc_info=True)
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
        logger.warning(f"[embeddings] Model '{EMBED_MODEL}' not listed in /api/tags at {ABI_LLM_BASE}. "
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
            logger.warning(f"[embeddings] attempt {attempt}/3 failed: {e}")
            time.sleep(backoff)
            backoff *= 2

    # If we reach here, all attempts failed
    logger.error("[embeddings] All attempts to get embedding failed", exc_info=last_exc)
    # Return empty tuple to signal failure to callers that check length/size
    return tuple()


def embed_one(text: str) -> List[float]:
    """Generate a single embedding for `text` using the local Ollama service.

    Behavior:
        - Returns a **normalized** embedding (unit-length).
        - Uses an internal LRU cache (size=1024) keyed by the exact text.
        - On repeated queries, avoids recomputing and hitting the backend.
        - On failure, returns an empty list [] and logs the error.

    Args:
        text (str): Input text to embed.

    Returns:
        list[float]:
            Normalized embedding vector.
            [] if the embedding could not be produced.
    """
    vec_t = _embed_one_cached(text)
    if not vec_t:
        # Keep caller’s logic simple: empty list means “no vector available”.
        return []
    return list(vec_t)


def embed_batch(texts: List[str]) -> List[List[float]]:
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
