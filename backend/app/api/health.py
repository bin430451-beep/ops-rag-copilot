from fastapi import APIRouter
router = APIRouter(tags=["health"])
@router.get("/healthz")
async def healthz():
    return {"status": "ok"}
@router.get("/readyz")
async def readyz():
    from app.rag.retriever import client
    from app.config import get_settings
    try:
        await client.get_collection(get_settings().qdrant_collection)
        qdrant_ok = True
    except Exception:
        qdrant_ok = False
    return {"status": "ready" if qdrant_ok else "degraded", "qdrant": qdrant_ok}
