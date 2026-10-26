import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)
from app.config import get_settings
from app.rag.embedder import embed_one, embed_texts
log = logging.getLogger(__name__)
_settings = get_settings()
client = AsyncQdrantClient(url=_settings.qdrant_url)
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
async def search(query: str, top_k: int | None = None, dept: str | None = None) -> list[dict]:
    qvec = await embed_one(query)
    flt = None
    if dept:
        flt = Filter(must=[FieldCondition(key="dept", match=MatchValue(value=dept))])
    hits = await client.query_points(
        collection_name=_settings.qdrant_collection,
        query=qvec,
        limit=top_k or _settings.retrieve_top_k,
        query_filter=flt,
        with_payload=True,
    )
    return [{"score": h.score, "text": h.payload.get("text", ""),
             "doc_name": h.payload.get("doc_name", ""),
             "doc_id": h.payload.get("doc_id", "")} for h in hits.points]
async def delete_doc(doc_id: str) -> None:
    await client.delete(
        collection_name=_settings.qdrant_collection,
        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )
