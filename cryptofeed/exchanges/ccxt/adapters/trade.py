"""Concrete trade adapters for CCXT data."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from cryptofeed.types import Trade

from .base import AdapterValidationError, BaseTradeAdapter, LOG


class CcxtTradeAdapter(BaseTradeAdapter):
    """CCXT implementation of the trade adapter."""

    def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
        try:
            payload = self._apply_trade_hooks(dict(raw_trade))
            self.validate_trade(payload)
            return Trade(
                exchange=self.exchange,
                symbol=self.normalize_symbol(payload["symbol"], payload),
                side=payload["side"],
                amount=Decimal(str(payload["amount"])),
                price=self.normalize_price(payload["price"], payload),
                timestamp=self.normalize_timestamp(payload["timestamp"], payload),
                id=payload["id"],
                raw=payload,
            )
        except (AdapterValidationError, Exception) as exc:  # pragma: no cover - defensive logging
            LOG.error("R3 trade conversion failed for %s: %s", self.exchange, exc)
            return None


class FallbackTradeAdapter(BaseTradeAdapter):
    """Fallback adapter that tolerates partial payloads."""

    def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
        try:
            payload = self._apply_trade_hooks(dict(raw_trade))
            symbol = payload.get("symbol")
            side = payload.get("side")
            if not symbol or not side:
                LOG.error("R3 fallback trade missing fields for %s: %s", self.exchange, payload)
                return None

            amount = payload.get("amount")
            price = payload.get("price")
            timestamp = payload.get("timestamp")
            trade_id = payload.get("id", "unknown")

            if amount is None or price is None:
                LOG.error("R3 fallback trade invalid amount/price for %s: %s", self.exchange, payload)
                return None

            normalized_ts = (
                self.normalize_timestamp(timestamp, payload)
                if timestamp is not None
                else 0.0
            )

            return Trade(
                exchange=self.exchange,
                symbol=self.normalize_symbol(symbol, payload),
                side=side,
                amount=Decimal(str(amount)),
                price=self.normalize_price(price, payload),
                timestamp=normalized_ts,
                id=str(trade_id),
                raw=payload,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            LOG.error("R3 fallback trade adapter failed for %s: %s", self.exchange, exc)
            return None
