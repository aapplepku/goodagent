"""Offline wall-deadline regressions retaining the real HTTP parser and I/O timeout."""

import asyncio
import json
from collections.abc import Iterable
from typing import Literal

import httpcore
import httpx
import pytest
from anyio.abc import ByteStream
from httpcore._backends.anyio import AnyIOStream
from httpcore._backends.base import SOCKET_OPTION
from pydantic import SecretStr
from starlette.types import Message, Receive, Scope, Send

from open_commerce.api.security import DemoSecurityMiddleware
from open_commerce.config import Settings
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.providers.openai_manager import OpenAIManagerProvider

Mode = Literal["trickle", "silent", "success"]


class ResponseBytes(ByteStream):
    def __init__(self, mode: Mode, entered: asyncio.Event) -> None:
        self.mode, self.entered = mode, entered
        self.first = True
        self.closed = False
        self.chunks = 0
        self.body = json.dumps(
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "phase": "final_answer",
                        "content": [{"type": "output_text", "text": "Synthetic answer"}],
                    }
                ],
            }
        ).encode()

    async def receive(self, max_bytes: int = 65536) -> bytes:
        if self.first:
            self.first = False
            length = (
                f"Content-Length: {len(self.body)}\r\n".encode()
                if self.mode == "success"
                else b"Transfer-Encoding: chunked\r\n"
            )
            return b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" + length + b"\r\n"
        self.entered.set()
        if self.mode == "success":
            return self.body
        await asyncio.sleep(0.05 if self.mode == "trickle" else 10)
        self.chunks += 1
        return b"1\r\n \r\n"

    async def send(self, item: bytes) -> None:
        pass

    async def send_eof(self) -> None:
        pass

    async def aclose(self) -> None:
        self.closed = True


class ByteBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, mode: Mode) -> None:
        self.mode = mode
        self.streams: list[ResponseBytes] = []
        self.entered = asyncio.Event()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 - httpcore backend interface
        local_address: str | None = None,
        socket_options: Iterable[SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        assert (host, port) == ("model-deadline.invalid", 80)
        stream = ResponseBytes(self.mode, self.entered)
        self.streams.append(stream)
        return AnyIOStream(stream)

    def transport(self) -> httpx.AsyncHTTPTransport:
        transport = httpx.AsyncHTTPTransport(trust_env=False)
        # Replace only the socket boundary, preserving HTTP parsing and native read timeouts.
        transport._pool = httpcore.AsyncConnectionPool(network_backend=self)
        return transport


class ModelFixture:
    def __init__(self, mode: Mode) -> None:
        self.backend = ByteBackend(mode)
        self.charges: list[tuple[int, int]] = []
        self.provider = OpenAIManagerProvider(
            api_key=SecretStr("synthetic-test-only"),
            model_id="deadline-test",
            base_url="http://model-deadline.invalid/v1",
            timeout_seconds=1,
            transport=self.backend.transport(),
            usage_guard=self.admit,
        )

    async def admit(self, input_bytes: int, output_tokens: int) -> None:
        self.charges.append((input_bytes, output_tokens))

    async def call(self) -> str | None:
        return (
            await self.provider.begin(
                instructions="Synthetic", messages=[], tools=[], max_output_tokens=128
            ).next([])
        ).content


async def test_trickling_responses_hit_wall_deadline_and_release_api_slots() -> None:
    fixture = ModelFixture("trickle")
    calls = 0

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal calls
        calls += 1
        if calls <= 2:
            with pytest.raises(ManagerModelUnavailableError):
                await fixture.call()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    middleware = DemoSecurityMiddleware(
        app, Settings(_env_file=None, runtime_profile="self_hosted", environment="test")
    )

    async def invoke() -> int:
        replies: list[Message] = []

        async def receive() -> Message:
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message: Message) -> None:
            replies.append(message)

        await middleware(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "path": "/v1/shopper/chat",
                "scheme": "http",
                "query_string": b"",
                "server": ("test", 80),
                "client": ("127.0.0.1", 1),
                "headers": [(b"host", b"test"), (b"content-type", b"application/json")],
            },
            receive,
            send,
        )
        return int(next(r["status"] for r in replies if r["type"] == "http.response.start"))

    tasks = [asyncio.create_task(invoke()), asyncio.create_task(invoke())]
    try:
        _, pending = await asyncio.wait(tasks, timeout=2.5)
        assert not pending, "Continuous body data must not extend the one-second wall deadline"
        assert [task.result() for task in tasks] == [200, 200]
        assert middleware.in_flight_expensive == 0
        assert await invoke() == 200
        assert len(fixture.charges) == 2
        assert len(fixture.backend.streams) == 2
        assert all(stream.closed and stream.chunks > 0 for stream in fixture.backend.streams)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_silent_body_uses_real_native_http_read_timeout() -> None:
    backend = ByteBackend("silent")
    async with asyncio.timeout(2.5):
        async with httpx.AsyncClient(transport=backend.transport(), timeout=1) as client:
            with pytest.raises(httpx.ReadTimeout):
                await client.post("http://model-deadline.invalid/responses", json={})
    assert len(backend.streams) == 1 and backend.streams[0].closed


@pytest.mark.parametrize("mode", ["silent", "success"])
async def test_provider_silent_timeout_and_normal_response_controls(mode: Mode) -> None:
    fixture = ModelFixture(mode)
    async with asyncio.timeout(2.5):
        if mode == "silent":
            with pytest.raises(ManagerModelUnavailableError):
                await fixture.call()
        else:
            assert await fixture.call() == "Synthetic answer"
    assert len(fixture.charges) == 1
    assert len(fixture.backend.streams) == 1 and fixture.backend.streams[0].closed


async def test_external_cancellation_propagates_and_closes_response_without_refund() -> None:
    fixture = ModelFixture("silent")
    task = asyncio.create_task(fixture.call())
    try:
        await asyncio.wait_for(fixture.backend.entered.wait(), timeout=2.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(fixture.charges) == 1
        assert len(fixture.backend.streams) == 1 and fixture.backend.streams[0].closed
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
