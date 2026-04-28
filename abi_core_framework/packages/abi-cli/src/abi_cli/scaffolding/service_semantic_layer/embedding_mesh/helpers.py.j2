import numpy as np
import threading

from typing import List, Dict, Any
from .models.models import SearchHit

_UPSERT_LOCK = threading.Lock()
_UPSERT_STORE: List[Dict[str, Any]] = []  # [{id, text, vector(np.array), metadata}]

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _search_upserts(query_vec: np.ndarray, top_k: int) -> List[SearchHit]:
    with _UPSERT_LOCK:
        if not _UPSERT_STORE:
            return []
        scored = []
        for row in _UPSERT_STORE:
            score = _cosine_sim(query_vec, row["vector"])
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for score, row in scored[:top_k]:
            hits.append(SearchHit(
                id=row["id"],
                score=score,
                text=row["text"],
                source="upsert",
                metadata=row.get("metadata"),
            ))
        return hits
