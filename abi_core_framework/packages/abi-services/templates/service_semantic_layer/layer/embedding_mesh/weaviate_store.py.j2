# -*- coding: utf-8 -*-
import json
import time

from typing import Any, Dict, Iterable, List
from weaviate.exceptions import WeaviateConnectionError
from weaviate.classes.config import Property, DataType
from . import weaviate_client


def get_client_with_retry(retries: int = 10, delay: float = 1.0):
    """Get a NEW Weaviate client connection with retry logic.
    
    Creates a fresh connection on each call. Caller is responsible for closing.
    """
    from . import weaviate_connection
    
    last: Exception | None = None
    for _ in range(retries):
        try:
            return weaviate_connection()
        except WeaviateConnectionError as e:
            last = e
            time.sleep(delay)
    raise last or RuntimeError(f'[!] Failed to connect to Weaviate!')

def ensure_collections()-> None:
    try:
        client = get_client_with_retry()
        existing_collections = list(client.collections.list_all().keys())
        
        if "AgentCard" not in existing_collections:
            client.collections.create(
                name="AgentCard",
                description="Agent card vectors",
                properties=[
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="uri", data_type=DataType.TEXT),
                    Property(name="origin", data_type=DataType.TEXT),
                    Property(name="metadata_json", data_type=DataType.TEXT)
                ]
            )
        
        if "MeshItem" not in existing_collections:
            client.collections.create(
                name="MeshItem",
                description="Ad-hoc upserted texts",
                properties=[
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="origin", data_type=DataType.TEXT),
                    Property(name="metadata_json", data_type=DataType.TEXT)
                ]
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
        count = 0
        with col.batch.dynamic() as batch:
            for it in items:
                batch.add_object(
                    properties={
                        "text": it["text"],
                        "uri": it.get("uri", ""),
                        "origin": it["origin"],
                        "metadata_json": json.dumps(it.get("metadata", {})),
                    },
                    vector=it["vector"],
                    uuid=it.get("id")
                )
                count += 1
        return count
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
        count = 0
        with col.batch.dynamic() as batch:
            for it in items:
                batch.add_object(
                    properties={
                        "text": it["text"],
                        "origin": "upsert",
                        "metadata_json": json.dumps(it.get("metadata", {})),
                    },
                    vector=it["vector"],
                    uuid=it.get("id"),
                )
                count += 1
        return count
    finally:
        client.close()

def get_existing_agent_card_uris() -> set:
    """Get set of URIs for all agent cards currently in Weaviate.
    
    Returns:
        set: Set of card URIs (file paths)
    """
    try:
        client = get_client_with_retry()
        col = client.collections.get("AgentCard")
        
        # Fetch all objects (no vector search, just get all)
        res = col.query.fetch_objects(limit=1000)
        
        uris = set()
        for o in res.objects:
            props = o.properties or {}
            uri = props.get("uri")
            if uri:
                uris.add(uri)
        
        return uris
    except Exception as e:
        # If collection doesn't exist or error, return empty set
        return set()
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
            metadata_json = props.get("metadata_json", "{}")
            try:
                metadata = json.loads(metadata_json)
            except:
                metadata = {}
            hits.append({
                "id": o.uuid,
                "score": 1.0 - float(o.metadata.distance or 0.0),  # convert distance→similarity
                "text": props.get("text", ""),
                "source": "agent_card",
                "metadata": metadata,
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
            metadata_json = props.get("metadata_json", "{}")
            try:
                metadata = json.loads(metadata_json)
            except:
                metadata = {}
            hits.append({
                "id": o.uuid,
                "score": 1.0 - float(o.metadata.distance or 0.0),
                "text": props.get("text", ""),
                "source": "upsert",
                "metadata": metadata,
            })
        return hits
    finally:
        client.close()