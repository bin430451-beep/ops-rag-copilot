import json
import logging
from typing import AsyncIterator
import httpx
from app.config import get_settings
log = logging.getLogger(__name__)
_settings = get_settings()
class LLMClient:
    """OpenAI 兼容 Chat Completions 客户端（vLLM / Ollama / Xinference 通用）。"""
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=_settings.llm_base_url.rstrip("/"),
            timeout=_settings.llm_timeout,
            headers={"Authorization": f"Bearer {_settings.llm_api_key}"},
        )
    async def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024) -> str:
        payload = {
            "model": _settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            r = await self._client.post("/chat/completions", json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            log.exception("LLM call failed: %s", e)
            raise

    async def chat_with_tools(self, messages: list[dict], tools: list[dict],
                              temperature: float = 0.2, max_tokens: int = 2048) -> dict:
        """Function Calling：返回完整 message dict（含 content 或 tool_calls）。"""
        payload = {
            "model": _settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
        }
        try:
            r = await self._client.post("/chat/completions", json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]
        except Exception as e:  # noqa: BLE001
            log.exception("LLM tool-call request failed: %s", e)
            raise
    async def stream(self, messages: list[dict], temperature: float = 0.2) -> AsyncIterator[str]:
        payload = {"model": _settings.llm_model, "messages": messages,
                   "temperature": temperature, "stream": True}
        async with self._client.stream("POST", "/chat/completions", json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    yield json.loads(data)["choices"][0]["delta"].get("content", "")
                except Exception:  # noqa: BLE001
                    continue
llm = LLMClient()
