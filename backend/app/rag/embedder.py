import logging
import httpx
from app.config import get_settings
log = logging.getLogger(__name__)
_settings = get_settings()
_client = httpx.AsyncClient(
    base_url=_settings.embedding_base_url.rstrip("/"),
    timeout=60,
    headers={"Authorization": f"Bearer {_settings.embedding_api_key}"},
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    r = await _client.post("/embeddings", json={
        "model": _settings.embedding_model,
        "input": texts,
    })
    r.raise_for_status()
    data = r.json()["data"]
    data.sort(key=lambda x: x["index"])
    return [d["embedding"] for d in data]
async def embed_one(text: str) -> list[float]:
    out = await embed_texts([text])
    return out[0]
