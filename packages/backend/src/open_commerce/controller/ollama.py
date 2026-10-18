"""The single model adapter: explicitly enabled, digest-pinned local Ollama."""

import asyncio
import json
import time
from typing import Literal

import httpx
from pydantic import Field

from open_commerce.config import Settings
from open_commerce.core.types import StrictDomainModel


class ModelUnavailableError(ValueError):
    """Local backend is disabled, unavailable or not the attested configuration."""


class InferenceResult(StrictDomainModel):
    content: str = Field(max_length=32768)
    backend: str = "ollama_local"
    model_id: str
    model_digest: str
    server_version: str
    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    provider_duration_ns: int | None = Field(default=None, ge=0)
    cost_usd: str = "0"
    cost_basis: str = "local inference: no provider fee; hardware/electricity unmeasured"
    source: Literal["real_model", "replay"] = "real_model"


class OllamaBackend:
    """No credentials, redirects, proxy inheritance, downloads or automatic retries."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def require_enabled(self) -> None:
        if not self.settings.model_enabled or not self.settings.model_local_only_attested:
            raise ModelUnavailableError("explicit local-only model opt-in is required")
        digest = self.settings.model_digest
        if (
            not digest.startswith("sha256:")
            or len(digest) != 71
            or any(c not in "0123456789abcdef" for c in digest[7:])
        ):
            raise ModelUnavailableError("the installed local model digest must be pinned")

    async def complete(
        self, *, messages: list[dict[str, str]], schema: dict[str, object]
    ) -> InferenceResult:
        self.require_enabled()
        settings = self.settings
        if len(json.dumps(messages, ensure_ascii=False).encode()) > settings.model_max_input_bytes:
            raise ValueError("model input byte limit exhausted")
        started = time.monotonic()
        async with asyncio.timeout(settings.model_timeout_seconds):
            async with httpx.AsyncClient(
                base_url=settings.model_url,
                trust_env=False,
                follow_redirects=False,
                timeout=settings.model_timeout_seconds,
            ) as client:
                version = await self._json(client, "GET", "/api/version")
                tags = await self._json(client, "GET", "/api/tags")
                models = tags.get("models")
                if not isinstance(models, list) or not any(
                    isinstance(m, dict)
                    and m.get("name") == settings.model_id
                    and str(m.get("digest", "")).removeprefix("sha256:")
                    == settings.model_digest.removeprefix("sha256:")
                    for m in models
                ):
                    raise ModelUnavailableError("pinned model is not installed locally")
                details = await self._json(
                    client, "POST", "/api/show", {"model": settings.model_id}
                )
                if details.get("remote_host") or details.get("remote_model"):
                    raise ModelUnavailableError("cloud relay models are not permitted")
                response = await self._json(
                    client,
                    "POST",
                    "/api/chat",
                    {
                        "model": settings.model_id,
                        "messages": messages,
                        "format": schema,
                        "stream": False,
                        "think": False,
                        "keep_alive": "5m",
                        "options": {
                            "temperature": 0,
                            "seed": 17,
                            "num_ctx": 32768,
                            "num_predict": settings.model_max_output_tokens,
                        },
                    },
                )
        message = response.get("message")
        if (
            response.get("done") is not True
            or response.get("done_reason") != "stop"
            or not isinstance(message, dict)
            or not isinstance(message.get("content"), str)
            or message.get("tool_calls")
        ):
            raise ValueError("incomplete or unexpected model response")
        prompt_tokens, output_tokens = response.get("prompt_eval_count"), response.get("eval_count")
        if type(prompt_tokens) is not int or type(output_tokens) is not int:
            raise ValueError("model token usage is missing")
        if output_tokens > settings.model_max_output_tokens:
            raise ValueError("model exceeded reserved output limit")
        return InferenceResult(
            content=message["content"],
            model_id=settings.model_id,
            model_digest=settings.model_digest,
            server_version=str(version.get("version", "unknown")),
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            provider_duration_ns=response.get("total_duration"),
        )

    @staticmethod
    async def _json(
        client: httpx.AsyncClient, method: str, path: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        async with client.stream(method, path, json=payload) as response:
            response.raise_for_status()
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 262144:
                    raise ValueError("model response byte limit exceeded")
        result: object = json.loads(chunks)
        if not isinstance(result, dict):
            raise ValueError("model response must be an object")
        return result
