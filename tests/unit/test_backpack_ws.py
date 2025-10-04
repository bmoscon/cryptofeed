from __future__ import annotations

import asyncio

import pytest
from yapic import json

from cryptofeed.exchanges.backpack.config import BackpackConfig, BackpackAuthSettings
from cryptofeed.exchanges.backpack.ws import BackpackSubscription, BackpackWsSession


class StubWebsocket:
    def __init__(self):
        self.open_called = False
        self.sent_messages: list[str] = []
        self.closed = False
        self._receive_queue: asyncio.Queue[str] = asyncio.Queue()

    async def open(self):
        self.open_called = True

    async def send(self, data: str):
        self.sent_messages.append(data)

    async def receive(self) -> str:
        return await self._receive_queue.get()

    async def close(self):
        self.closed = True

    def queue_message(self, payload: str) -> None:
        self._receive_queue.put_nowait(payload)


@pytest.mark.asyncio
async def test_ws_session_sends_auth_on_open():
    config = BackpackConfig(
        enable_private_channels=True,
        auth=BackpackAuthSettings(
            api_key="api",
            public_key="".join(f"{i:02x}" for i in range(32)),
            private_key="".join(f"{i:02x}" for i in range(32)),
        ),
    )
    stub = StubWebsocket()
    session = BackpackWsSession(config, conn_factory=lambda: stub, heartbeat_interval=0)

    await session.open()

    assert stub.open_called is True
    assert stub.sent_messages, "Expected auth payload to be sent"
    auth_payload = json.loads(stub.sent_messages[0])
    assert auth_payload["op"] == "auth"
    assert auth_payload["headers"]["X-API-Key"] == "api"


@pytest.mark.asyncio
async def test_ws_session_subscribe_sends_payload():
    config = BackpackConfig()
    stub = StubWebsocket()
    session = BackpackWsSession(config, conn_factory=lambda: stub, heartbeat_interval=0)

    await session.open()
    await session.subscribe([BackpackSubscription(channel="trades", symbols=["BTC-USDT"])])

    assert len(stub.sent_messages) >= 1
    subscribe_payload = json.loads(stub.sent_messages[-1])
    assert subscribe_payload["op"] == "subscribe"
    assert subscribe_payload["channels"][0]["symbols"] == ["BTC-USDT"]


@pytest.mark.asyncio
async def test_ws_session_reauth_on_private_subscribe():
    config = BackpackConfig(
        enable_private_channels=True,
        auth=BackpackAuthSettings(
            api_key="api",
            public_key="".join(f"{i:02x}" for i in range(32)),
            private_key="".join(f"{i:02x}" for i in range(32)),
        ),
    )
    stub = StubWebsocket()
    session = BackpackWsSession(config, conn_factory=lambda: stub, heartbeat_interval=0)

    await session.open()
    stub.sent_messages.clear()

    await session.subscribe([
        BackpackSubscription(channel="orders", symbols=["BTC-USDT"], private=True)
    ])

    # Expect subscribe + auth messages in that order
    assert len(stub.sent_messages) == 2
    subscribe_payload = json.loads(stub.sent_messages[0])
    assert subscribe_payload["op"] == "subscribe"
    reauth_payload = json.loads(stub.sent_messages[1])
    assert reauth_payload["op"] == "auth"


@pytest.mark.asyncio
async def test_ws_session_refreshes_auth_window():
    config = BackpackConfig(
        enable_private_channels=True,
        auth=BackpackAuthSettings(
            api_key="api",
            public_key="".join(f"{i:02x}" for i in range(32)),
            private_key="".join(f"{i:02x}" for i in range(32)),
        ),
    )
    stub = StubWebsocket()
    session = BackpackWsSession(config, conn_factory=lambda: stub, heartbeat_interval=0)

    await session.open()
    await session.subscribe([
        BackpackSubscription(channel="orders", symbols=["BTC-USDT"], private=True)
    ])
    stub.sent_messages.clear()
    session._last_auth_timestamp_us = 0

    await session._maybe_refresh_auth()

    assert stub.sent_messages
    assert json.loads(stub.sent_messages[-1])["op"] == "auth"


@pytest.mark.asyncio
async def test_ws_session_read_uses_stub_receive():
    config = BackpackConfig()
    stub = StubWebsocket()
    session = BackpackWsSession(config, conn_factory=lambda: stub, heartbeat_interval=0)

    await session.open()
    stub.queue_message('{"type": "trade"}')
    message = await session.read()
    assert message == '{"type": "trade"}'


@pytest.mark.asyncio
async def test_ws_session_close():
    config = BackpackConfig()
    stub = StubWebsocket()
    session = BackpackWsSession(config, conn_factory=lambda: stub, heartbeat_interval=0)

    await session.open()
    await session.close()

    assert stub.closed is True
