import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)
from app.config import get_settings
from app.rag.embedder import embed_one, embed_texts
from app.rag.bm25 import BM25Index, rrf_fuse
log = logging.getLogger(__name__)
_settings = get_settings()
client = AsyncQdrantClient(url=_settings.qdrant_url)

_bm25 = BM25Index()
_bm25_ready = False


async def ensure_collection() -> None:
    exists = await client.collection_exists(_settings.qdrant_collection)
    if not exists:
        await client.create_collection(
            collection_name=_settings.qdrant_collection,
            vectors_config=VectorParams(size=_settings.embedding_dim, distance=Distance.COSINE),
        )
        log.info("Created collection %s", _settings.qdrant_collection)


async def upsert_chunks(doc_id: str, doc_name: str, chunks: list[str], dept: str = "public") -> int:
    vectors = await embed_texts(chunks)
    points = [
        PointStruct(
            id=f"{doc_id}-{i}",
            vector=vec,
            payload={"doc_id": doc_id, "doc_name": doc_name, "dept": dept,
                     "chunk_index": i, "text": chunks[i]},
        )
        for i, vec in enumerate(vectors)
    ]
    await client.upsert(collection_name=_settings.qdrant_collection, points=points)
    return len(points)


async def _ensure_bm25() -> None:
    """懒加载：首次混合检索时从 Qdrant 全量构建 BM25 倒排索引。"""
    global _bm25_ready
    if _bm25_ready:
        return
    try:
        offset = None
        while True:
            res = await client.scroll(
                collection_name=_settings.qdrant_collection,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for pt in res.points:
                _bm25.add_document(str(pt.id), pt.payload.get("text", "") or "")
            if not res.next_page_offset:
                break
            offset = res.next_page_offset
        _bm25.build()
        _bm25_ready = True
        log.info("BM25 index ready")
    except Exception as e:  # noqa: BLE001
        log.warning("BM25 index unavailable, fallback to vector-only: %s", e)
        _bm25_ready = False


async def search(query: str, top_k: int | None = None, dept: str | None = None) -> list[dict]:
    limit = top_k or _settings.retrieve_top_k
    flt = None
    if dept:
        flt = Filter(must=[FieldCondition(key="dept", match=MatchValue(value=dept))])

    qvec = await embed_one(query)
    hits = await client.query_points(
        collection_name=_settings.qdrant_collection,
        query=qvec,
        limit=limit,
        query_filter=flt,
        with_payload=True,
    )
    vec_hits = [
        {"score": h.score, "text": h.payload.get("text", ""),
         "doc_name": h.payload.get("doc_name", ""),
         "doc_id": h.payload.get("doc_id", ""),
         "point_id": str(h.id)} for h in hits.points
    ]

    if not _settings.hybrid_enabled:
        return vec_hits

    await _ensure_bm25()
    if not _bm25_ready:
        return vec_hits

    bm_ranked = _bm25.search(query, top_k=limit * 2)
    if not bm_ranked:
        return vec_hits

    bm_pool = {d["point_id"]: d for d in vec_hits}
    bm_hits: list[dict] = []
    for pid, score in bm_ranked:
        base = bm_pool.get(pid)
        if base:
            d = dict(base)
            d["bm25_score"] = score
            bm_hits.append(d)
        else:
            try:
                recs = await client.retrieve(
                    collection_name=_settings.qdrant_collection, ids=[pid], with_payload=True
                )
                if recs:
                    p = recs[0].payload
                    bm_hits.append({
                        "score": 0.0, "text": p.get("text", ""),
                        "doc_name": p.get("doc_name", ""), "doc_id": p.get("doc_id", ""),
                        "point_id": pid, "bm25_score": score,
                    })
            except Exception:  # noqa: BLE001
                continue
    if not bm_hits:
        return vec_hits

    fused = rrf_fuse([vec_hits, bm_hits])
    return fused[:limit]


async def delete_doc(doc_id: str) -> None:
    await client.delete(
        collection_name=_settings.qdrant_collection,
        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )
