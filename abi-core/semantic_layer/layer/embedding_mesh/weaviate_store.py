# -*- coding: utf-8 -*-
import time

from typing import Any, Dict, Iterable, List
from weaviate.exceptions import WeaviateConnectionError
from weaviate.classes.config import Property, DataType, Configure, VectorDistances
from . import weaviate_client


def get_client_with_retry(retries: int = 10, delay: float = 1.0):
    last: Exception | None = None
    for _ in range(retries):
        try:
            client = weaviate_client()
            client.connect()
            return client
        except WeaviateConnectionError as e:
            last = e
            time.sleep(delay)
    raise last or RuntimeError(f'[!] Failed to connect to Weaviate!')

def ensure_collections()-> None:
    try:
        client = get_client_with_retry()
        if "AgentCard" not in [c.name for c in client.collections.list_all()]:
            client.collections.create(
                name="AgentCard",
                description="Agent card vectors",
                properties=[
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="uri", data_type=DataType.TEXT),
                    Property(name="origin", data_type=DataType.TEXT),
                    Property(name="metadata", data_type=DataType.OBJECT)
                ],
                vectorizer_config=Configure.Vectorize.none(),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance=VectorDistances.COSINE
                )
            )
        
        if "MeshItem" not in [c.name for c in client.collections.list_all()]:
            client.collections.create(
                name="MeshItem",
                description="Ad-hoc upserted texts",
                properties=[
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="origin", data_type=DataType.TEXT),
                    Property(name="metadata", data_type=DataType.OBJECT)
                ],
                vectorizer_config=Configure.Vectorize.none(),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance=VectorDistances.COSINE
                )
            )
    finally:
        client.close()

def upsert_agent_cards(
        items: Iterable[Dict[str, Any]]
) -> int:
    """
    items: Iterable dicts:
        - id (str) opcional can be use like a UUID
        - text (str)
        - uri (str)
        - metadata (str) optional
        - vector (List[float]) needed
    """

    try:
        client = get_client_with_retry()
        col = client.collections.get("AgentCard")
        with col.batch.dynamic() as batch:
            for it in items:
                batch.add_object(
                    properties={
                        "text": it["text"],
                        "uri": it.get("uri", ""),
                        "origin": it["origin"],
                        "metadata": it.get("metadata", {}),
                    },
                    vector=it["vector"],
                    uuid=it.get("id")
                )
        return len(list(items))
    finally:
        client.close()

def upsert_mesh_items(
        items: Iterable[Dict[str, Any]]
) -> int:
    """
    Items: Iterable dicts:
    - id (str) optional
    - text (str) 
    - metadata (str) optinal
    - vector (List[float])
    """
    try:
        client = get_client_with_retry()
        col = client.collections.get("MeshItem")
        with col.batch.dynamic() as batch:
            for it in items:
                batch.add_object(
                    properties={
                        "text": it["text"],
                        "origin": "upsert",
                        "metadata": it.get("metadata", {}),
                    },
                    vector=it["vector"],
                    uuid=it.get("id"),
                )
        return len(list(items))
    finally:
        client.close()

def search_agent_cards(
        query_vector: List[float], top_k: int = 5
) -> List[Dict[str, Any]]:
    try:
        client = get_client_with_retry()
        col = client.collections.get("AgentCard")
        res = col.query.near_vector(
            near_vector=query_vector, limit=top_k, return_metadata=["distance"]
        )
        hits = []
        for o in res.objects:
            props = o.properties or {}
            hits.append({
                "id": o.uuid,
                "score": 1.0 - float(o.metadata.distance or 0.0),  # convertir distancia→similaridad
                "text": props.get("text", ""),
                "source": "agent_card",
                "metadata": props.get("metadata"),
                "uri": props.get("uri"),
            })
        return hits
    finally:
        client.close()

def search_upserts(
    query_vector: List[float], top_k: int = 5
) -> List[Dict[str, Any]]:
    try:
        client = get_client_with_retry()
        col = client.collections.get("MeshItem")
        res = col.query.near_vector(
            near_vector=query_vector, limit=top_k, return_metadata=["distance"]
        )
        hits = []
        for o in res.objects:
            props = o.properties or {}
            hits.append({
                "id": o.uuid,
                "score": 1.0 - float(o.metadata.distance or 0.0),
                "text": props.get("text", ""),
                "source": "upsert",
                "metadata": props.get("metadata"),
            })
        return hits
    finally:
        client.close()
