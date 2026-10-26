"""Agent 工具注册表：Function Calling 可调用的工具定义与执行器。

所有工具均为「查询 / 分析」类，不执行任何系统命令，保证内网环境安全。
"""
import json
import logging
from datetime import datetime
from app.rag import retriever, reranker
from app.store import meta_db
log = logging.getLogger(__name__)


async def _search_kb(query: str, top_k: int = 5, dept: str | None = None) -> str:
    hits = await retriever.search(query, dept=dept)
    if not hits:
        return "知识库无命中结果。"
    hits = await reranker.rerank(query, hits, top_n=max(1, min(top_k, len(hits))))
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"[{i}] 文档《{h['doc_name']}》\n{h['text'][:500]}")
    return "\n\n".join(parts)


def _extract_log_lines(raw_logs: str, max_lines: int = 80) -> str:
    from app.agent.alert_agent import extract_log_lines as _extract
    return _extract(raw_logs, max_lines)


def _get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _list_documents() -> str:
    docs = meta_db.list_documents()
    if not docs:
        return "知识库暂无文档。"
    return "\n".join(
        f"- {d['doc_name']}（doc_id={d['doc_id']}，status={d['status']}）" for d in docs
    )


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "在企业运维知识库中检索与问题相关的文档片段，用于获取排查依据",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词或完整问题"},
                    "top_k": {"type": "integer", "description": "返回片段数量，默认 5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_log_lines",
            "description": "从原始日志中按关键字（error/fail/timeout/exception 等）提取关键行，控制分析范围",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_logs": {"type": "string", "description": "原始日志文本"},
                    "max_lines": {"type": "integer", "description": "最多保留行数，默认 80"},
                },
                "required": ["raw_logs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取服务器当前时间，用于结合时间窗口判断告警时效",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "列出知识库中已上传的文档清单及审核状态",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_TOOL_IMPL = {
    "search_kb": _search_kb,
    "extract_log_lines": _extract_log_lines,
    "get_current_time": _get_current_time,
    "list_documents": _list_documents,
}

_ASYNC_TOOLS = {"search_kb"}


async def execute_tool(name: str, args: dict) -> str:
    """执行工具并返回可回填给 LLM 的文本结果。"""
    if name not in _TOOL_IMPL:
        return f"未知工具：{name}"
    try:
        fn = _TOOL_IMPL[name]
        result = await fn(**args) if name in _ASYNC_TOOLS else fn(**args)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except TypeError as e:
        log.warning("Tool %s bad args %s: %s", name, args, e)
        return f"工具参数错误：{e}"
    except Exception as e:  # noqa: BLE001
        log.exception("Tool %s failed: %s", name, e)
        return f"工具执行失败：{e}"
