from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.security import require_api_key
from app.core.llm import llm
from app.rag import retriever, reranker
from app.agent.prompts import RAG_ANSWER_PROMPT, FALLBACK_MESSAGE
router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_api_key)])
class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = 5
    dept: str | None = None
class QueryOut(BaseModel):
    answer: str
    references: list[dict]
    degraded: bool = False
@router.post("/query", response_model=QueryOut)
async def query(body: QueryIn):
    hits = await retriever.search(body.question, dept=body.dept)
    if not hits:
        return QueryOut(answer="知识库中暂未找到相关内容，请先上传对应文档。", references=[])
    hits = await reranker.rerank(body.question, hits, top_n=body.top_k)
    context = "\n\n".join(f"[{h['doc_name']}] {h['text'][:800]}" for h in hits)
    prompt = RAG_ANSWER_PROMPT.format(context=context, question=body.question)
    try:
        answer = await llm.chat([{"role": "user", "content": prompt}])
        return QueryOut(answer=answer, references=hits)
    except Exception:
        return QueryOut(answer=FALLBACK_MESSAGE, references=hits, degraded=True)
