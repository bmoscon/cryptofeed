"""Tests for CCXT trade and order book adapters."""
from __future__ import annotations

from decimal import Decimal

import pytest

from cryptofeed.defines import BID, ASK
from cryptofeed.exchanges.ccxt.adapters import CcxtTradeAdapter, CcxtOrderBookAdapter


class TestCcxtTradeAdapter:
    """Tests for CCXT trade conversion."""

    def test_convert_trade_normalizes_fields(self):
        adapter = CcxtTradeAdapter(exchange="backpack")

        trade = adapter.convert_trade(
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": "0.0105",
                "price": "42123.45",
                "timestamp": 1700000000456,
                "id": "trade-1",
                "sequence": 99,
            }
        )

        assert trade is not None
        assert trade.exchange == "backpack"
        assert trade.symbol == "BTC-USDT"
        assert trade.amount == Decimal("0.0105")
        assert trade.price == Decimal("42123.45")
        assert trade.timestamp == pytest.approx(1700000000.456)
        assert trade.id == "trade-1"
        assert trade.raw["sequence"] == 99

    def test_convert_trade_missing_fields_returns_none(self, caplog):
        adapter = CcxtTradeAdapter()

        trade = adapter.convert_trade({"symbol": "BTC/USDT", "side": "buy"})

        assert trade is None
        assert any("Missing required field" in message for message in caplog.messages)


class TestCcxtOrderBookAdapter:
    """Tests for CCXT order book conversion."""

    def test_convert_orderbook_sets_sequence_and_precision(self):
        adapter = CcxtOrderBookAdapter(exchange="backpack")

        order_book = adapter.convert_orderbook(
            {
                "symbol": "ETH/USDT",
                "timestamp": 1700001000123,
                "nonce": 555,
                "bids": [["2500.1", "1.5"], ["2500.0", "0.25"]],
                "asks": [["2500.5", "0.4"], ["2501.0", "0.75"]],
            }
        )

        assert order_book is not None
        assert order_book.exchange == "backpack"
        assert order_book.symbol == "ETH-USDT"
        assert order_book.timestamp == pytest.approx(1700001000.123)
        bids = dict(order_book.book[BID])
        asks = dict(order_book.book[ASK])
        assert bids[Decimal("2500.1")] == Decimal("1.5")
        assert asks[Decimal("2500.5")] == Decimal("0.4")
        assert getattr(order_book, "sequence_number", None) == 555

    def test_convert_orderbook_missing_required_returns_none(self, caplog):
        adapter = CcxtOrderBookAdapter()

        order_book = adapter.convert_orderbook(
            {
                "symbol": "ETH/USDT",
                "bids": "invalid",
                "asks": [],
            }
        )

        assert order_book is None
        assert any("Missing required field" in message or "Bids must be a list" in message for message in caplog.messages)
