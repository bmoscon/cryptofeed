"""Tests for the CCXT adapter registry and base adapters."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

import pytest

from cryptofeed.exchanges.ccxt.adapters import (
    AdapterHookRegistry,
    AdapterRegistry,
    AdapterValidationError,
    BaseOrderBookAdapter,
    BaseTradeAdapter,
    CcxtOrderBookAdapter,
    CcxtTradeAdapter,
    FallbackOrderBookAdapter,
    FallbackTradeAdapter,
    ccxt_orderbook_hook,
    ccxt_trade_hook,
)
from cryptofeed.types import OrderBook, Trade


@pytest.fixture(autouse=True)
def reset_hooks() -> None:
    AdapterHookRegistry.reset()
    yield
    AdapterHookRegistry.reset()


class TestAdapterRegistry:
    """Registry registration, lookup, and fallback behaviour."""

    def test_registry_provides_defaults(self):
        registry = AdapterRegistry()
        trade_adapter = registry.get_trade_adapter("unknown")
        book_adapter = registry.get_orderbook_adapter("another")

        assert isinstance(trade_adapter, CcxtTradeAdapter)
        assert trade_adapter.exchange == "unknown"
        assert isinstance(book_adapter, CcxtOrderBookAdapter)

    def test_registry_registers_custom_adapter(self):
        class CustomTradeAdapter(CcxtTradeAdapter):
            pass

        registry = AdapterRegistry()
        registry.register_trade_adapter("binance", CustomTradeAdapter)

        adapter = registry.get_trade_adapter("binance")
        assert isinstance(adapter, CustomTradeAdapter)

    def test_registry_rejects_invalid_adapter(self):
        registry = AdapterRegistry()
        with pytest.raises(AdapterValidationError):
            registry.register_trade_adapter("binance", type("Foo", (), {}))

    def test_registry_convert_trade_uses_fallback(self):
        class BrokenTradeAdapter(CcxtTradeAdapter):
            def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
                return None

        registry = AdapterRegistry()
        registry.register_trade_adapter("broken", BrokenTradeAdapter)

        trade = registry.convert_trade(
            "broken",
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 1,
                "price": 20000,
                "timestamp": 1700000000000,
                "id": "t-1",
            },
        )

        assert isinstance(trade, Trade)
        assert trade.symbol == "BTC-USDT"


class TestBaseAdapters:
    """Base adapter utilities and extension points."""

    def test_base_trade_adapter_normalization(self):
        class SimpleAdapter(BaseTradeAdapter):
            def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
                self.validate_trade(raw_trade)
                return Trade(
                    exchange=self.exchange,
                    symbol=self.normalize_symbol(raw_trade["symbol"]),
                    side=raw_trade["side"],
                    amount=Decimal(str(raw_trade["amount"])),
                    price=Decimal(str(raw_trade["price"])),
                    timestamp=self.normalize_timestamp(raw_trade["timestamp"]),
                    id=raw_trade["id"],
                    raw=raw_trade,
                )

        adapter = SimpleAdapter(exchange="example")
        trade = adapter.convert_trade(
            {
                "symbol": "ETH/USDT",
                "side": "sell",
                "amount": 1,
                "price": 1800,
                "timestamp": 1700000000000,
                "id": "t-1",
            }
        )

        assert trade is not None
        assert trade.symbol == "ETH-USDT"
        assert trade.timestamp == pytest.approx(1700000000.0)

    def test_base_orderbook_adapter_validation(self):
        class SimpleBookAdapter(BaseOrderBookAdapter):
            def convert_orderbook(self, raw: Dict[str, Any]):
                self.validate_orderbook(raw)
                return None

        adapter = SimpleBookAdapter()
        with pytest.raises(AdapterValidationError):
            adapter.validate_orderbook({"symbol": "BTC/USDT", "bids": "bad", "asks": []})


class TestConcreteAdapters:
    """Concrete adapter behaviour tests."""

    def test_trade_adapter_returns_none_on_missing_fields(self, caplog):
        adapter = CcxtTradeAdapter()
        assert adapter.convert_trade({"symbol": "BTC/USDT", "side": "buy"}) is None
        assert any("R3 trade validation failed" in msg for msg in caplog.messages)

    def test_orderbook_adapter_handles_sequence(self):
        adapter = CcxtOrderBookAdapter(exchange="demo")
        order_book = adapter.convert_orderbook(
            {
                "symbol": "BTC/USDT",
                "timestamp": 1700000000456,
                "sequence": 42,
                "bids": [["50000", "1"]],
                "asks": [["50010", "2"]],
            }
        )

        assert order_book is not None
        assert getattr(order_book, "sequence_number", None) == 42


class TestFallbackAdapters:
    """Graceful handling for partial payloads."""

    def test_fallback_trade_adapter_handles_missing_price(self, caplog):
        adapter = FallbackTradeAdapter()
        trade = adapter.convert_trade({"symbol": "BTC/USDT", "side": "buy"})
        assert trade is None
        assert any("R3 fallback trade" in msg for msg in caplog.messages)

    def test_fallback_orderbook_adapter_skips_empty(self, caplog):
        adapter = FallbackOrderBookAdapter()
        book = adapter.convert_orderbook({"symbol": "BTC/USDT", "bids": [], "asks": []})
        assert book is None
        assert any("R3 fallback empty order book" in msg for msg in caplog.messages)


class TestHooks:
    """Hook registration and normalisation overrides."""

    def test_trade_hook_mutates_payload_and_normalizers(self):
        registry = AdapterRegistry()

        @ccxt_trade_hook(
            "demo",
            symbol=lambda normalized, raw, payload: normalized.replace("-TEST", "-USD"),
            timestamp=lambda normalized, raw, payload: normalized / 1000.0,
        )
        def adjust_trade(payload: Dict[str, Any]) -> Dict[str, Any]:
            payload = dict(payload)
            payload["symbol"] = payload["symbol"] + "-TEST"
            payload["timestamp"] = payload["timestamp"] * 1000
            return payload

        trade = registry.convert_trade(
            "demo",
            {
                "symbol": "ETH/USDT",
                "side": "buy",
                "amount": "0.1",
                "price": 2000,
                "timestamp": 1700000000,
                "id": "tx-1",
            },
        )

        assert isinstance(trade, Trade)
        assert trade.symbol.endswith("USD")
        assert trade.timestamp == pytest.approx(1700000.0)

    def test_orderbook_hook_customises_price_levels(self):
        registry = AdapterRegistry()

        def adjust_orderbook(payload: Dict[str, Any]) -> Dict[str, Any]:
            payload = dict(payload)
            payload["bids"].append(["100", "1"])
            payload["asks"].append(["110", "1"])
            return payload

        registry.register_orderbook_hook("demo", adjust_orderbook)
        registry.register_orderbook_normalizer(
            "demo",
            "price_levels",
            lambda normalized, raw_levels, payload: {
                price: size * 2 for price, size in normalized.items()
            },
        )

        book = registry.convert_orderbook(
            "demo",
            {
                "symbol": "BTC/USDT",
                "bids": [["100", "0.5"]],
                "asks": [["110", "0.25"]],
            },
        )

        assert isinstance(book, OrderBook)
        assert book.book.bids[Decimal("100")] == Decimal("2")
        assert book.book.asks[Decimal("110")] == Decimal("2")
