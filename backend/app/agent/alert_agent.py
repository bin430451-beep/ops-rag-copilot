import logging
from app.core.llm import llm
from app.rag import retriever, reranker
from app.agent.prompts import ALERT_ANALYSIS_PROMPT
log = logging.getLogger(__name__)
LOG_KEYWORDS = ("error", "fail", "timeout", "exception", "refused", "oom", "panic")
def extract_log_lines(raw_logs: str, max_lines: int = 80) -> str:
    """从原始日志中提取关键字行，控制 prompt 长度。"""
    lines = [ln for ln in raw_logs.splitlines() if ln.strip()]
    picked = [ln for ln in lines if any(k in ln.lower() for k in LOG_KEYWORDS)]
    if not picked:
        picked = lines[-max_lines:]
    return "\n".join(picked[-max_lines:])
async def analyze_alert(alert: str, raw_logs: str = "", top_k: int = 3) -> dict:
    logs = extract_log_lines(raw_logs) if raw_logs else "(无日志输入)"
    hits = await retriever.search(alert, top_k=10)
    hits = await reranker.rerank(alert, hits, top_n=top_k)
    context = "\n\n".join(
        f"[{h['doc_name']}] {h['text'][:600]}" for h in hits
    ) or "(知识库无命中)"
    prompt = ALERT_ANALYSIS_PROMPT.format(alert=alert, logs=logs, context=context)
    try:
        answer = await llm.chat([{"role": "user", "content": prompt}])
    except Exception:  # noqa: BLE001
        answer = "【降级】大模型不可用，以下为知识库命中原文，请人工判断：\n" + context
    return {"analysis": answer, "references": hits}
