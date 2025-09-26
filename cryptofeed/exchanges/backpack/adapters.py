"""Backpack message adapters converting raw payloads to cryptofeed types."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from cryptofeed.defines import ASK, BID
from cryptofeed.types import OrderBook, Trade, Ticker


def _microseconds_to_seconds(value: Optional[int | float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) / 1_000_000.0 if value > 1_000_000 else float(value)


@dataclass(slots=True)
class TradePayload:
    symbol: str
    price: Decimal
    amount: Decimal
    side: Optional[str]
    trade_id: Optional[str]
    sequence: Optional[int]
    timestamp: Optional[float]
    raw: dict


class BackpackTradeAdapter:
    """Convert Backpack trade payloads into cryptofeed Trade objects."""

    def __init__(self, exchange: str):
        self._exchange = exchange

    def parse(self, payload: dict, *, normalized_symbol: str) -> Trade:
        trade = self._parse_payload(payload, normalized_symbol)
        return Trade(
            exchange=self._exchange,
            symbol=trade.symbol,
            side=trade.side,
            amount=trade.amount,
            price=trade.price,
            timestamp=trade.timestamp or 0.0,
            id=trade.trade_id,
            raw=payload,
        )

    def _parse_payload(self, payload: dict, normalized_symbol: str) -> TradePayload:
        price = Decimal(str(payload.get("price") or payload.get("p")))
        amount = Decimal(str(payload.get("size") or payload.get("q")))
        timestamp = payload.get("timestamp") or payload.get("ts")
        sequence = payload.get("sequence") or payload.get("s")
        trade_id = payload.get("id") or payload.get("t")

        return TradePayload(
            symbol=normalized_symbol,
            price=price,
            amount=amount,
            side=payload.get("side"),
            trade_id=str(trade_id) if trade_id is not None else None,
            sequence=sequence,
            timestamp=_microseconds_to_seconds(timestamp),
            raw=payload,
        )


class BackpackOrderBookAdapter:
    """Maintain Backpack order book state and emit cryptofeed OrderBook objects."""

    def __init__(self, exchange: str, *, max_depth: int = 0):
        self._exchange = exchange
        self._max_depth = max_depth
        self._books: Dict[str, OrderBook] = {}

    def apply_snapshot(
        self,
        *,
        normalized_symbol: str,
        bids: Iterable[Iterable],
        asks: Iterable[Iterable],
        timestamp: Optional[int | float] = None,
        sequence: Optional[int] = None,
        raw: Optional[dict] = None,
    ) -> OrderBook:
        bids_processed = {
            Decimal(str(level[0])): Decimal(str(level[1]))
            for level in bids
        }
        asks_processed = {
            Decimal(str(level[0])): Decimal(str(level[1]))
            for level in asks
        }

        order_book = OrderBook(
            exchange=self._exchange,
            symbol=normalized_symbol,
            bids=bids_processed,
            asks=asks_processed,
            max_depth=self._max_depth,
        )
        order_book.timestamp = _microseconds_to_seconds(timestamp)
        order_book.sequence_number = sequence
        order_book.raw = raw
        self._books[normalized_symbol] = order_book
        return order_book

    def apply_delta(
        self,
        *,
        normalized_symbol: str,
        bids: Iterable[Iterable] | None,
        asks: Iterable[Iterable] | None,
        timestamp: Optional[int | float],
        sequence: Optional[int],
        raw: Optional[dict],
    ) -> OrderBook:
        if normalized_symbol not in self._books:
            raise KeyError(f"No snapshot for symbol {normalized_symbol}")

        book = self._books[normalized_symbol]
        if bids:
            self._update_levels(book, BID, bids)
        if asks:
            self._update_levels(book, ASK, asks)

        book.timestamp = _microseconds_to_seconds(timestamp)
        book.sequence_number = sequence
        book.delta = {
            BID: [tuple(self._normalize_level(level)) for level in bids] if bids else [],
            ASK: [tuple(self._normalize_level(level)) for level in asks] if asks else [],
        }
        book.raw = raw
        return book

    def _normalize_level(self, level: Iterable) -> List[Decimal]:
        price, size = level[0], level[1]
        return [Decimal(str(price)), Decimal(str(size))]

    def _update_levels(self, book: OrderBook, side: str, levels: Iterable[Iterable]):
        price_map = book.book.bids if side == BID else book.book.asks
        for level in levels:
            price = Decimal(str(level[0]))
            size = Decimal(str(level[1]))
            if size == 0:
                if price in price_map:
                    del price_map[price]
            else:
                price_map[price] = size


class BackpackTickerAdapter:
    """Convert Backpack ticker payloads into cryptofeed Ticker objects."""

    def __init__(self, exchange: str):
        self._exchange = exchange

    def parse(self, payload: dict, *, normalized_symbol: str) -> Ticker:
        last_raw = payload.get("last") or payload.get("price")
        last_price = Decimal(str(last_raw)) if last_raw is not None else Decimal("0")
        bid_val = payload.get("bestBid") or payload.get("bid")
        ask_val = payload.get("bestAsk") or payload.get("ask")
        bid_dec = Decimal(str(bid_val)) if bid_val is not None else last_price
        ask_dec = Decimal(str(ask_val)) if ask_val is not None else last_price
        timestamp = _microseconds_to_seconds(payload.get("timestamp") or payload.get("ts")) or 0.0

        return Ticker(
            exchange=self._exchange,
            symbol=normalized_symbol,
            bid=bid_dec,
            ask=ask_dec,
            timestamp=timestamp,
            raw=payload,
        )
