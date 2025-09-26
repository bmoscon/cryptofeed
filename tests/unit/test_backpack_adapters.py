from __future__ import annotations

from decimal import Decimal

import pytest

from cryptofeed.defines import ASK, BID
from cryptofeed.exchanges.backpack.adapters import BackpackOrderBookAdapter, BackpackTradeAdapter


def test_trade_adapter_parses_payload():
    adapter = BackpackTradeAdapter(exchange="BACKPACK")
    payload = {
        "p": "30000",
        "q": "0.5",
        "side": "buy",
        "t": "trade-id",
        "ts": 1_700_000_000_000,
    }

    trade = adapter.parse(payload, normalized_symbol="BTC-USDT")

    assert trade.exchange == "BACKPACK"
    assert trade.symbol == "BTC-USDT"
    assert trade.amount == Decimal("0.5")
    assert trade.price == Decimal("30000")
    assert trade.id == "trade-id"
    assert trade.timestamp == pytest.approx(1_700_000.0)


def test_order_book_adapter_snapshot_and_delta():
    adapter = BackpackOrderBookAdapter(exchange="BACKPACK")

    snapshot = adapter.apply_snapshot(
        normalized_symbol="BTC-USDT",
        bids=[["30000", "1"]],
        asks=[["30010", "2"]],
        timestamp=1_700_000_000_000,
        sequence=100,
        raw={"type": "snapshot"},
    )

    assert snapshot.sequence_number == 100
    assert snapshot.book.bids[Decimal("30000")] == Decimal("1")
    assert snapshot.book.asks[Decimal("30010")] == Decimal("2")

    delta = adapter.apply_delta(
        normalized_symbol="BTC-USDT",
        bids=[["30000", "0"], ["29990", "1.5"]],
        asks=None,
        timestamp=1_700_000_000_500,
        sequence=101,
        raw={"type": "delta"},
    )

    assert Decimal("30000") not in delta.book.bids
    assert delta.book.bids[Decimal("29990")] == Decimal("1.5")
    assert delta.sequence_number == 101
    assert delta.delta[BID][0][0] == Decimal("30000")
    assert delta.delta[ASK] == []
