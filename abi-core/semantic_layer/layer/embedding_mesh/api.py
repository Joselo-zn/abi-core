from starlette.responses import JSONResponse
from starlette.routing import Route

from .helpers import _UPSERT_LOCK, _UPSERT_STORE

from .embeddings_abi import (
    build_agent_card_embeddings,
    get_embed_model_name,
    clear_caches,
    embed_texts
)
from .models.models import (
    MeshResetResponse,
    MeshStatsResponse,
)

from .weaviate_store import (
    search_agent_cards,
    ensure_collections,
    upsert_agent_cards,
    upsert_mesh_items,
    search_upserts,
)


async def mesh_build(request) -> JSONResponse:
    body = await request.json()
    force = bool(body.get("forceReload", False))
    df = build_agent_card_embeddings(force_reload=force)  # df con columnas: card_uri, agent_card, maybe text/title
    count = 0
    if df is not None and len(df) > 0:
        # Serializa el “texto” base de cada card (elige qué campo embebes)
        texts = []
        items = []
        for _, row in df.iterrows():
            txt = row.get("text") or row.get("title") or str(row.get("agent_card"))
            texts.append(txt)
        vecs = embed_texts(texts)
        # Empaqueta para upsert
        for i, (_, row) in enumerate(df.iterrows()):
            items.append({
                "id": None,  # usa UUID auto
                "text": texts[i],
                "uri": row.get("card_uri", ""),
                "metadata": {"card_uri": row.get("card_uri")},
                "vector": vecs[i],
            })
        count = upsert_agent_cards(items)

    return JSONResponse({"source":"agent_cards","items":count,"model":get_embed_model_name()})

async def mesh_upsert(request) -> JSONResponse:
    body = await request.json()
    items = body.get("items", [])
    texts = [it["text"] for it in items]
    vecs = embed_texts(texts)
    payload = []
    for it, v in zip(items, vecs):
        payload.append({
            "id": it.get("id"),
            "text": it["text"],
            "metadata": it.get("metadata", {}),
            "vector": v,
        })
    n = upsert_mesh_items(payload)
    return JSONResponse({"upserted": n, "model": get_embed_model_name()})

async def mesh_search(request) -> JSONResponse:
    body = await request.json()
    query = body["query"]
    topk = int(body.get("topK", 5))
    qv = embed_texts([query])[0]

    agent_hits = search_agent_cards(qv, top_k=topk)
    upsert_hits = search_upserts(qv, top_k=topk)

    all_hits = sorted(agent_hits + upsert_hits, key=lambda x: x["score"], reverse=True)[:topk]
    return JSONResponse({"hits": all_hits, "model": get_embed_model_name()})

async def mesh_reset(request) -> JSONResponse:
    # cleans cache from embedding module and store ad-hoc
    clear_caches()
    with _UPSERT_LOCK:
        _UPSERT_STORE.clear()
    return JSONResponse(MeshResetResponse(cleared=True).dict())


async def mesh_stats(request) -> JSONResponse:
    # best-effort: si no hay df, cuenta 0
    df = build_agent_card_embeddings(force_reload=False)
    agent_count = 0 if df is None else len(df)
    with _UPSERT_LOCK:
        upsert_count = len(_UPSERT_STORE)
    return JSONResponse(MeshStatsResponse(
        model=get_embed_model_name(),
        agentCardsCount=agent_count,
        upsertCount=upsert_count,
    ).dict())


def attach_embedding_mesh_routes(app) -> None:
    """
    Registry routes app Starlette/ASGI:
      POST /mesh/build
      POST /mesh/upsert
      POST /mesh/search
      POST /mesh/reset
      GET  /mesh/stats
    """
    ensure_collections()
    app.router.routes.extend([
        Route("/mesh/build",  endpoint=mesh_build,  methods=["POST"]),
        Route("/mesh/upsert", endpoint=mesh_upsert, methods=["POST"]),
        Route("/mesh/search", endpoint=mesh_search, methods=["POST"]),
        Route("/mesh/reset",  endpoint=mesh_reset,  methods=["POST"]),
        Route("/mesh/stats",  endpoint=mesh_stats,  methods=["GET"]),
    ])
    