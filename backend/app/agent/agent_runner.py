"""Agent 编排循环：LLM 自主决策 → 工具调用 → 结果回填 → 收敛答案。

支持 Function Calling（OpenAI 兼容 tools 协议），带最大步数保护与降级兜底。
"""
import json
import logging
from app.core.llm import llm as default_llm
from app.agent.memory import memory as default_memory
from app.agent.tools import TOOLS_SCHEMA, execute_tool
log = logging.getLogger(__name__)

MAX_STEPS = 6

AGENT_SYSTEM_PROMPT = """你是企业内网的资深 SRE 智能体，负责协助运维人员完成故障分析与知识问答。
你可以调用以下工具获取事实依据：
- search_kb：检索企业运维知识库（SOP / 手册）
- extract_log_lines：从原始日志中提取关键字行
- get_current_time：获取当前时间
- list_documents：查看知识库文档清单

规则：
1. 优先调用工具获取依据，再基于工具结果回答，不要臆测
2. 用简洁中文输出，结构尽量使用：【现象】/【可能原因】/【建议操作】
3. 工具结果不足以支撑结论时，明确说明"知识库未覆盖"或"信息不足"
4. 不要编造日志内容、监控数据或命令执行结果
5. 多轮对话中记得结合上下文，回答当前问题即可"""


async def run_agent(
    question: str,
    session_id: str | None = None,
    top_k: int = 5,
    llm_client=None,
    memory_store=None,
    max_steps: int = MAX_STEPS,
) -> dict:
    client = llm_client or default_llm
    mem = memory_store or default_memory

    messages = mem.get(session_id) if session_id else []
    if not messages:
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": question})

    trace: list[dict] = []
    for step in range(1, max_steps + 1):
        try:
            msg = await client.chat_with_tools(messages, TOOLS_SCHEMA)
        except Exception as e:  # noqa: BLE001
            log.exception("Agent LLM call failed at step %d: %s", step, e)
            return {
                "answer": f"大模型服务不可用，已中断 Agent 推理（第 {step} 步）。",
                "trace": trace,
                "degraded": True,
            }

        tool_calls = msg.get("tool_calls")
        if tool_calls:
            messages.append(msg)
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments") or "{}"
                trace.append({"step": step, "tool": name, "args": raw_args})
                try:
                    args = json.loads(raw_args)
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}
                result = await execute_tool(name, args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.get("id", ""), "content": result}
                )
            continue

        content = msg.get("content") or ""
        messages.append({"role": "assistant", "content": content})
        if session_id:
            mem.save(session_id, messages)
        return {"answer": content, "trace": trace, "degraded": False}

    return {
        "answer": "已达到最大推理步数，建议将问题拆分后重试或补充日志/上下文。",
        "trace": trace,
        "degraded": True,
    }
