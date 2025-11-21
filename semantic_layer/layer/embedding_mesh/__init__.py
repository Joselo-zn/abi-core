# semantic_layer/embedding_mesh/__init__.py
import os
import weaviate


def _get_weaviate_url() -> str:
    return os.getenv("WEAVIATE_URL", "http://weaviate:8080")

def weaviate_client() -> weaviate.WeaviateClient:
    url = _get_weaviate_url()
    host = url.split("://")[1].split(":")[0]
    port = int(url.rsplit(":", 1)[-1])
    # 🔑 no pases grpc_port si no lo usas
    return weaviate.connect_to_local(
        host=host,
        port=port,
        #grpc_port=50051,
    )
