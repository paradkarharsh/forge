"""Ollama LLM provider adapter.

Communicates with a local Ollama instance via its HTTP API.
No external SDK required — uses ``httpx`` which is already a FastAPI
dependency.  Provider SDK NEVER leaks outside this module.
"""
import logging
import time

import httpx

from forge_api.domain.llm import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    StreamDelta,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Provider adapter for a local Ollama instance."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def complete(self, request: ChatRequest) -> ChatResponse:
        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
        ]
        payload = {
            "model": request.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
            },
        }
        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat", json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        duration_ms = (time.monotonic() - start) * 1000

        content = data.get("message", {}).get("content", "")
        usage_raw = data.get("eval_count", 0)
        prompt_count = data.get("prompt_eval_count", 0)
        return ChatResponse(
            content=content,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=prompt_count,
                output_tokens=usage_raw,
                total_tokens=prompt_count + usage_raw,
            ),
            model=data.get("model", request.model),
            provider="ollama",
            duration_ms=duration_ms,
        )

    async def stream(
        self, request: ChatRequest,
    ) -> "OllamaStreamIterator":
        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
        ]
        payload = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": request.temperature,
            },
        }
        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        client = httpx.AsyncClient(timeout=self._timeout)
        response = await client.send(
            client.build_request("POST", f"{self._base_url}/api/chat", json=payload),
            stream=True,
        )
        response.raise_for_status()
        return OllamaStreamIterator(response, client)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


class OllamaStreamIterator:
    """Wraps the Ollama streaming NDJSON response."""

    def __init__(self, response: httpx.Response, client: httpx.AsyncClient) -> None:
        self._response = response
        self._client = client
        self._lines = response.aiter_lines()
        self._done = False

    def __aiter__(self) -> "OllamaStreamIterator":
        return self

    async def __anext__(self) -> StreamDelta:
        import json

        if self._done:
            raise StopAsyncIteration

        try:
            line = await self._lines.__anext__()
        except StopAsyncIteration:
            self._done = True
            await self._cleanup()
            raise

        if not line.strip():
            return StreamDelta(content="")

        data = json.loads(line)
        if data.get("done", False):
            self._done = True
            await self._cleanup()
            usage_raw = data.get("eval_count", 0)
            prompt_count = data.get("prompt_eval_count", 0)
            return StreamDelta(
                content=data.get("message", {}).get("content", ""),
                finish_reason=FinishReason.STOP,
                usage=TokenUsage(
                    input_tokens=prompt_count,
                    output_tokens=usage_raw,
                    total_tokens=prompt_count + usage_raw,
                ),
            )

        content = data.get("message", {}).get("content", "")
        return StreamDelta(content=content)

    async def _cleanup(self) -> None:
        try:
            await self._response.aclose()
        except Exception:
            pass
        try:
            await self._client.aclose()
        except Exception:
            pass
