import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.core.security import require_api_key
from app.core.llm import llm
from app.rag import retriever, reranker
from app.agent.prompts import RAG_ANSWER_PROMPT, FALLBACK_MESSAGE
from app.agent.agent_runner import run_agent
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


class AgentQueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    top_k: int = 5


class AgentQueryOut(BaseModel):
    answer: str
    trace: list[dict] = []
    degraded: bool = False


@router.post("/agent", response_model=AgentQueryOut)
async def agent_query(body: AgentQueryIn):
    """Agent 模式：LLM 自主调用工具（知识库检索 / 日志提取 / 时间等），支持多轮会话。"""
    result = await run_agent(body.question, session_id=body.session_id, top_k=body.top_k)
    return AgentQueryOut(**result)


@router.post("/stream")
async def stream_query(body: QueryIn):
    """SSE 流式问答：检索 → 重排 → LLM 逐字输出，失败自动降级为兜底话术。"""
    async def _gen():
        hits = await retriever.search(body.question, dept=body.dept)
        if not hits:
            yield _sse({"delta": "知识库中暂未找到相关内容，请先上传对应文档。"})
            yield "data: [DONE]\n\n"
            return
        hits = await reranker.rerank(body.question, hits, top_n=body.top_k)
        context = "\n\n".join(f"[{h['doc_name']}] {h['text'][:800]}" for h in hits)
        prompt = RAG_ANSWER_PROMPT.format(context=context, question=body.question)
        try:
            async for chunk in llm.stream([{"role": "user", "content": prompt}]):
                if chunk:
                    yield _sse({"delta": chunk})
        except Exception:  # noqa: BLE001
            yield _sse({"delta": FALLBACK_MESSAGE})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
