import logging
import httpx
from app.config import get_settings
log = logging.getLogger(__name__)
_settings = get_settings()
_client = httpx.AsyncClient(timeout=30)
async def rerank(query: str, docs: list[dict], top_n: int | None = None) -> list[dict]:
    if not _settings.rerank_enabled or not docs:
        return docs[: top_n or _settings.rerank_top_n]
    payload = {
        "model": _settings.rerank_model,
        "query": query,
        "texts": [d["text"] for d in docs],
        "top_n": top_n or _settings.rerank_top_n,
    }
    try:
        r = await _client.post(_settings.rerank_url, json=payload)
        r.raise_for_status()
        results = r.json()
        ranked = sorted(results, key=lambda x: x["score"], reverse=True)
        out = []
        for item in ranked[: top_n or _settings.rerank_top_n]:
            d = dict(docs[item["index"]])
            d["rerank_score"] = item["score"]
            out.append(d)
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("Rerank failed, fallback to vector order: %s", e)
        return docs[: top_n or _settings.rerank_top_n]
