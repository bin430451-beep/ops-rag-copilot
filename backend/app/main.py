import logging
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.core.security import IPWhitelistMiddleware
from app.api import chat, kb, ops, health
from app.store import meta_db
from app.rag import retriever
_settings = get_settings()
logging.basicConfig(
    level=_settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
app = FastAPI(
    title="OpsRAG Copilot",
    version="0.1.0",
    description="Private-cloud AIOps & RAG knowledge copilot",
)
app.add_middleware(IPWhitelistMiddleware)
app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(kb.router, prefix="/api/v1")
app.include_router(ops.router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
@app.on_event("startup")
async def _startup() -> None:
    meta_db.init_db()
    try:
        await retriever.ensure_collection()
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).warning("Qdrant not ready at startup: %s", e)
@app.get("/")
async def index():
    return FileResponse("app/static/index.html")
