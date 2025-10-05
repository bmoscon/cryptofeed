from __future__ import annotations

import asyncio
import base64
from typing import Any

import pytest

from cryptofeed.exchanges.native.auth import Ed25519AuthHelper, Ed25519Credentials
from cryptofeed.exchanges.native.metrics import NativeExchangeMetrics
from cryptofeed.exchanges.native.rest import NativeRestClient, NativeRestError
from cryptofeed.exchanges.native.router import NativeMessageRouter
from cryptofeed.exchanges.native.symbols import NativeMarket, NativeSymbolService
from cryptofeed.exchanges.native.ws import NativeSubscription, NativeWsSession


class FakeHTTPConn:
    def __init__(self, response: str) -> None:
        self._response = response
        self.closed = False

    async def read(self, url: str, params: Any = None) -> str:
        return self._response

    async def close(self) -> None:
        self.closed = True


class FakeWSConn:
    def __init__(self) -> None:
        self.opened = False
        self.sent = []
        self.closed = False

    async def _open(self) -> None:
        self.opened = True

    async def read(self):
        if False:
            yield None  # pragma: no cover - iterator signature only
        return

    async def write(self, data: str) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True


def _ed25519_keypair() -> bytes:
    return bytes(range(32))


def test_ed25519_auth_helper_builds_headers() -> None:
    creds = Ed25519Credentials(
        api_key="key",
        private_key=_ed25519_keypair(),
        passphrase="pass",
    )
    helper = Ed25519AuthHelper(credentials=creds)
    headers = helper.build_headers(method="GET", path="/test", body="{}", timestamp_us=123456)
    assert headers["X-API-Key"] == "key"
    assert headers["X-Signature"]


@pytest.mark.asyncio
async def test_native_rest_client_read_json_success() -> None:
    client = NativeRestClient(
        exchange="dummy",
        exchange_id="dummy",
        http_conn_factory=lambda: FakeHTTPConn('{"status": "ok"}')
    )
    try:
        data = await client.read_json("http://example")
        assert data["status"] == "ok"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_native_rest_client_read_json_failure() -> None:
    client = NativeRestClient(
        exchange="dummy",
        exchange_id="dummy",
        http_conn_factory=lambda: FakeHTTPConn('not-json')
    )
    with pytest.raises(NativeRestError):
        await client.read_json("http://example")


@pytest.mark.asyncio
async def test_native_ws_session_open_send_close() -> None:
    metrics = NativeExchangeMetrics()
    session = NativeWsSession(
        endpoint="wss://example",
        exchange="dummy",
        exchange_id="dummy",
        conn_factory=lambda: FakeWSConn(),
        metrics=metrics,
        heartbeat_interval=0.0,
    )
    await session.open()
    await session.subscribe([NativeSubscription(channel="trades", symbols=["BTC-USD"])])
    await session.send({"op": "ping"})
    await session.close()


class DummyRestClient:
    def __init__(self, markets: list[dict[str, Any]]) -> None:
        self._markets = markets
        self.calls = 0

    async def fetch_markets(self) -> list[dict[str, Any]]:
        self.calls += 1
        return list(self._markets)


class DummySymbolService(NativeSymbolService):
    market_class = NativeMarket

    def __init__(self, rest_client: DummyRestClient, *, ttl_seconds: int = 60) -> None:
        super().__init__(rest_client=rest_client, ttl_seconds=ttl_seconds)

    async def _fetch_markets(self):
        return await self._rest_client.fetch_markets()

    def _include_market(self, entry: dict[str, Any]) -> bool:
        return entry.get("status", "TRADING") == "TRADING"

    def _normalize_symbol(self, native_symbol: str, entry: dict[str, Any]) -> str:
        return native_symbol.replace("_", "-")


@pytest.mark.asyncio
async def test_native_symbol_service_caches_and_maps_symbols() -> None:
    rest_client = DummyRestClient(
        markets=[
            {"symbol": "BTC_USDT", "status": "TRADING"},
            {"symbol": "ETH_USDT", "status": "HALTED"},
        ]
    )
    service = DummySymbolService(rest_client, ttl_seconds=3600)

    await service.ensure()
    assert rest_client.calls == 1

    market = service.get_market("BTC-USDT")
    assert market.normalized_symbol == "BTC-USDT"
    assert service.native_symbol("BTC-USDT") == "BTC_USDT"
    assert service.normalized_symbol("BTC_USDT") == "BTC-USDT"

    await service.ensure()
    assert rest_client.calls == 1  # cached due to TTL

    await service.ensure(force=True)
    assert rest_client.calls == 2

    with pytest.raises(KeyError):
        service.get_market("ETH-USDT")


class DummyMetrics:
    def __init__(self) -> None:
        self.parser_errors = 0
        self.dropped_messages = 0

    def record_parser_error(self) -> None:
        self.parser_errors += 1

    def record_dropped_message(self) -> None:
        self.dropped_messages += 1


class DummyRouter(NativeMessageRouter):
    def __init__(self, metrics: DummyMetrics):
        super().__init__(metrics=metrics)
        self._received: list[dict[str, Any]] = []
        self.register_handler("trade", self._handle_trade)

    @property
    def received(self) -> list[dict[str, Any]]:
        return self._received

    async def _handle_trade(self, payload: dict[str, Any]) -> None:
        self._received.append(payload)


@pytest.mark.asyncio
async def test_native_message_router_dispatch_and_drop() -> None:
    metrics = DummyMetrics()
    router = DummyRouter(metrics)

    await router.dispatch({"channel": "trade", "symbol": "BTC_USDT"})
    assert router.received[0]["symbol"] == "BTC_USDT"

    await router.dispatch({"channel": "unknown", "payload": 1})
    await router.dispatch({"payload": 2})

    assert metrics.parser_errors == 2
    assert metrics.dropped_messages == 2
