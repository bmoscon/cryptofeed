"""Legacy type adapter utilities for direct dict conversions."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from cryptofeed.types import OrderBook, Trade
from cryptofeed.defines import BID, ASK


class CcxtTypeAdapter:
    """Static helpers for converting CCXT payloads to cryptofeed types."""

    @staticmethod
    def to_cryptofeed_trade(ccxt_trade: Dict[str, Any], exchange: str) -> Trade:
        symbol = ccxt_trade["symbol"].replace("/", "-")
        timestamp = float(ccxt_trade["timestamp"]) / 1000.0
        return Trade(
            exchange=exchange,
            symbol=symbol,
            side=ccxt_trade["side"],
            amount=Decimal(str(ccxt_trade["amount"])),
            price=Decimal(str(ccxt_trade["price"])),
            timestamp=timestamp,
            id=ccxt_trade["id"],
            raw=ccxt_trade,
        )

    @staticmethod
    def to_cryptofeed_orderbook(ccxt_book: Dict[str, Any], exchange: str) -> OrderBook:
        symbol = ccxt_book["symbol"].replace("/", "-")
        timestamp = (
            float(ccxt_book["timestamp"]) / 1000.0
            if ccxt_book.get("timestamp") is not None
            else None
        )

        bids = {Decimal(str(price)): Decimal(str(amount)) for price, amount in ccxt_book["bids"]}
        asks = {Decimal(str(price)): Decimal(str(amount)) for price, amount in ccxt_book["asks"]}

        order_book = OrderBook(exchange=exchange, symbol=symbol, bids=bids, asks=asks)
        order_book.timestamp = timestamp
        order_book.raw = ccxt_book
        return order_book

    @staticmethod
    def normalize_symbol_to_ccxt(symbol: str) -> str:
        return symbol.replace("-", "/")


__all__ = ["CcxtTypeAdapter"]
