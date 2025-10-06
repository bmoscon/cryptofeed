"""Concrete order book adapters for CCXT data."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from cryptofeed.defines import BID, ASK
from cryptofeed.types import OrderBook

from .base import AdapterValidationError, BaseOrderBookAdapter, LOG


class CcxtOrderBookAdapter(BaseOrderBookAdapter):
    """CCXT implementation of the order book adapter."""

    def convert_orderbook(self, raw_orderbook: Dict[str, Any]) -> Optional[OrderBook]:
        try:
            payload = self._apply_orderbook_hooks(dict(raw_orderbook))
            self.validate_orderbook(payload)

            symbol = self.normalize_symbol(payload["symbol"], payload)
            timestamp = (
                self.normalize_timestamp(payload.get("timestamp"), payload)
                if payload.get("timestamp") is not None
                else None
            )

            bids = self.normalize_prices(payload["bids"], payload)
            asks = self.normalize_prices(payload["asks"], payload)

            book = OrderBook(
                exchange=self.exchange,
                symbol=symbol,
                bids=bids,
                asks=asks,
            )

            book.timestamp = timestamp
            sequence = (
                payload.get("nonce")
                or payload.get("sequence")
                or payload.get("seq")
            )
            if sequence is not None:
                try:
                    book.sequence_number = int(sequence)
                except (TypeError, ValueError):
                    book.sequence_number = sequence
            book.raw = payload
            return book
        except (AdapterValidationError, Exception) as exc:  # pragma: no cover
            LOG.error(
                "R3 order book conversion failed for %s: %s", self.exchange, exc
            )
            return None


class FallbackOrderBookAdapter(BaseOrderBookAdapter):
    """Fallback adapter that handles partially populated books."""

    def convert_orderbook(self, raw_orderbook: Dict[str, Any]) -> Optional[OrderBook]:
        try:
            payload = self._apply_orderbook_hooks(dict(raw_orderbook))
            symbol = payload.get("symbol")
            if not symbol:
                LOG.error(
                    "R3 fallback order book missing symbol for %s: %s",
                    self.exchange,
                    payload,
                )
                return None

            bids = payload.get("bids", [])
            asks = payload.get("asks", [])
            if not bids and not asks:
                LOG.warning("R3 fallback empty order book for %s", symbol)
                return None

            bid_dict = {}
            ask_dict = {}
            for price, size in bids:
                try:
                    bid_dict[Decimal(str(price))] = Decimal(str(size))
                except (TypeError, ValueError):
                    continue
            for price, size in asks:
                try:
                    ask_dict[Decimal(str(price))] = Decimal(str(size))
                except (TypeError, ValueError):
                    continue

            book = OrderBook(
                exchange=self.exchange,
                symbol=self.normalize_symbol(symbol, payload),
                bids=bid_dict,
                asks=ask_dict,
            )

            timestamp = payload.get("timestamp")
            if timestamp is not None:
                book.timestamp = self.normalize_timestamp(timestamp, payload)
            book.raw = payload
            return book
        except Exception as exc:  # pragma: no cover
            LOG.error(
                "R3 fallback order book adapter failed for %s: %s",
                self.exchange,
                exc,
            )
            return None
