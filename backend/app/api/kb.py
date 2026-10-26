import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from app.config import get_settings
from app.core.security import require_api_key
from app.rag import retriever
from app.rag.ingest import parse_file, SUPPORTED
from app.rag.splitter import split_text
from app.store import meta_db
router = APIRouter(prefix="/kb", tags=["knowledge-base"], dependencies=[Depends(require_api_key)])
_settings = get_settings()
class UploadOut(BaseModel):
    doc_id: str
    doc_name: str
    chunks: int
@router.post("/upload", response_model=UploadOut)
async def upload(
    file: UploadFile = File(...),
    dept: str = Form("public"),
):
    if Path(file.filename).suffix.lower() not in SUPPORTED:
        raise HTTPException(400, f"unsupported file type, allowed: {sorted(SUPPORTED)}")
    data = await file.read()
    text = parse_file(file.filename, data)
    if not text.strip():
        raise HTTPException(400, "empty or unparsable document")
    chunks = split_text(text, _settings.chunk_size, _settings.chunk_overlap)
    if not chunks:
        raise HTTPException(400, "no chunk generated")
    doc_id = uuid.uuid4().hex[:12]
    await retriever.ensure_collection()
    n = await retriever.upsert_chunks(doc_id, file.filename, [c.text for c in chunks], dept=dept)
    meta_db.add_document(doc_id, file.filename, dept=dept)
    return UploadOut(doc_id=doc_id, doc_name=file.filename, chunks=n)
@router.get("/documents")
async def documents():
    return meta_db.list_documents()
@router.post("/documents/{doc_id}/approve")
async def approve(doc_id: str):
    meta_db.set_status(doc_id, "approved")
    return {"doc_id": doc_id, "status": "approved"}
@router.delete("/documents/{doc_id}")
async def delete(doc_id: str):
    await retriever.delete_doc(doc_id)
    meta_db.delete_document(doc_id)
    return {"doc_id": doc_id, "deleted": True}
