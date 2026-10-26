import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.agent.agent_runner import run_agent
from app.agent.memory import SessionMemory


class FakeLLM:
    """按顺序返回预设响应的 mock LLM。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def chat_with_tools(self, messages, tools, **kwargs):
        self.calls += 1
        if not self.responses:
            return {"role": "assistant", "content": "（无更多响应）"}
        return self.responses.pop(0)


def _tool_call(name, args="{}"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": f"call_{name}", "type": "function",
             "function": {"name": name, "arguments": args}}
        ],
    }


def test_agent_tool_call_then_answer():
    fake = FakeLLM([
        _tool_call("get_current_time"),
        {"role": "assistant", "content": "已获取当前时间，可结合时间窗口分析。"},
    ])
    result = _run(fake)
    assert result["degraded"] is False
    assert "当前时间" in result["answer"] or "时间" in result["answer"]
    assert len(result["trace"]) == 1
    assert result["trace"][0]["tool"] == "get_current_time"


def test_agent_direct_answer_no_tool():
    fake = FakeLLM([{"role": "assistant", "content": "直接回答，无需工具。"}])
    result = _run(fake)
    assert result["degraded"] is False
    assert result["answer"] == "直接回答，无需工具。"
    assert result["trace"] == []


def test_agent_llm_failure_degraded():
    class BoomLLM:
        async def chat_with_tools(self, messages, tools, **kwargs):
            raise RuntimeError("llm down")
    result = _run(BoomLLM())
    assert result["degraded"] is True
    assert "大模型服务不可用" in result["answer"]


def test_agent_max_steps_guard():
    fake = FakeLLM([_tool_call("get_current_time")] * 10)
    result = _run(fake, max_steps=3)
    assert result["degraded"] is True
    assert "最大推理步数" in result["answer"]
    assert fake.calls >= 3


def test_agent_memory_preserved():
    fake = FakeLLM([{"role": "assistant", "content": "第一轮回答。"}])
    mem = SessionMemory()
    result = _run(fake, session_id="s1", memory_store=mem)
    assert result["degraded"] is False
    stored = mem.get("s1")
    assert stored and stored[-1]["content"] == "第一轮回答。"


def _run(client, session_id=None, memory_store=None, max_steps=None):
    import asyncio
    kwargs = dict(llm_client=client, session_id=session_id, memory_store=memory_store)
    if max_steps:
        kwargs["max_steps"] = max_steps
    return asyncio.run(run_agent("测试问题", **kwargs))
