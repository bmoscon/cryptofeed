'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed.defines import ASK, BID, BUY, CANDLES, FUNDING, INDEX, L1_BOOK, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, SELL, TICKER, TRADES
from cryptofeed.symbols import str_to_symbol


EPOCH_LOW = 1_400_000_000     # 2014-05
EPOCH_HIGH = 2_100_000_000    # 2036-07

MONEY = ('price', 'amount', 'bid', 'ask', 'open', 'close', 'high', 'low', 'volume', 'open_interest', 'rate', 'predicted_rate', 'mark_price', 'leverage', 'quantity')
BOOKS = (L2_BOOK, L3_BOOK)


class Violations(list):
    def report(self, limit: int = 12) -> str:
        unique = sorted(set(self))
        head = '\n  '.join(unique[:limit])
        more = f'\n  ... and {len(unique) - limit} more' if len(unique) > limit else ''
        return f'{len(self)} invariant violations ({len(unique)} unique):\n  {head}{more}'


class PlaybackValidator:
    def __init__(self, exchange: str, candle_interval: str = None):
        self.exchange = exchange
        self.candle_interval = candle_interval
        self.violations = Violations()
        self._sequences = {}
        self.sequence_resets = 0

    def callbacks(self, channels) -> dict:
        return {channel: self._make(channel) for channel in channels}

    def _fail(self, channel, symbol, message):
        self.violations.append(f'{self.exchange}/{channel} {symbol}: {message}')

    def _make(self, channel):
        async def _callback(obj, receipt_timestamp):
            self.check(channel, obj, receipt_timestamp)
        return _callback

    def _timestamp(self, channel, symbol, value, field):
        if not isinstance(value, float):
            self._fail(channel, symbol, f'{field} is {type(value).__name__} {value!r}, expected float')
        elif not (EPOCH_LOW < value < EPOCH_HIGH):
            self._fail(channel, symbol, f'{field} {value} is outside a sane epoch window')

    def check(self, channel, obj, receipt_timestamp):
        symbol = getattr(obj, 'symbol', '?')

        if obj.exchange != self.exchange:
            self._fail(channel, symbol, f'exchange is {obj.exchange!r}, expected {self.exchange!r}')

        try:
            str_to_symbol(symbol)
        except Exception as e:
            self._fail(channel, symbol, f'symbol does not parse: {type(e).__name__}: {e}')

        self._timestamp(channel, symbol, receipt_timestamp, 'receipt_timestamp')
        timestamp = getattr(obj, 'timestamp', None)
        if timestamp is not None:
            self._timestamp(channel, symbol, timestamp, 'timestamp')

        for field in MONEY:
            value = getattr(obj, field, None)
            if value is not None and not isinstance(value, Decimal):
                self._fail(channel, symbol, f'{field} is {type(value).__name__}, expected Decimal')

        if channel == TRADES:
            if obj.side not in (BUY, SELL):
                self._fail(channel, symbol, f'side is {obj.side!r}, expected {BUY!r} or {SELL!r}')
            if obj.amount is not None and obj.amount <= 0:
                self._fail(channel, symbol, f'trade amount is {obj.amount}')
            if obj.price is not None and obj.price <= 0:
                self._fail(channel, symbol, f'trade price is {obj.price}')

        elif channel in (TICKER, L1_BOOK):
            bid, ask = obj.bid, obj.ask
            if bid and ask and bid > ask:
                self._fail(channel, symbol, f'crossed: bid {bid} > ask {ask}')

        elif channel == CANDLES:
            self._timestamp(channel, symbol, obj.start, 'start')
            self._timestamp(channel, symbol, obj.stop, 'stop')
            if isinstance(obj.start, float) and isinstance(obj.stop, float) and obj.start >= obj.stop:
                self._fail(channel, symbol, f'candle start {obj.start} >= stop {obj.stop}')
            if self.candle_interval and obj.interval != self.candle_interval:
                self._fail(channel, symbol, f'interval is {obj.interval!r}, subscribed {self.candle_interval!r}')
            if obj.high is not None and obj.low is not None and obj.high < obj.low:
                self._fail(channel, symbol, f'candle high {obj.high} < low {obj.low}')

        elif channel == LIQUIDATIONS:
            if obj.side not in (BUY, SELL):
                self._fail(channel, symbol, f'side is {obj.side!r}')

        elif channel == OPEN_INTEREST:
            if obj.open_interest is not None and obj.open_interest < 0:
                self._fail(channel, symbol, f'open interest is {obj.open_interest}')

        elif channel == INDEX:
            if obj.price is not None and obj.price <= 0:
                self._fail(channel, symbol, f'index price is {obj.price}')

        elif channel == FUNDING:
            if obj.next_funding_time is not None:
                self._timestamp(channel, symbol, obj.next_funding_time, 'next_funding_time')

        elif channel in BOOKS:
            self._check_book(channel, obj)

    def _check_book(self, channel, book):
        symbol = book.symbol
        bids, asks = book.book.bids, book.book.asks

        # cross_check=True makes the library raise on a crossed book, so reaching here means the top of book is sane
        if len(bids) and len(asks):
            best_bid, best_ask = bids.index(0)[0], asks.index(0)[0]
            if best_bid >= best_ask:
                self._fail(channel, symbol, f'crossed book: best bid {best_bid} >= best ask {best_ask}')

        for side, levels in ((BID, bids), (ASK, asks)):
            for index in range(min(len(levels), 5)):
                price, size = levels.index(index)
                if not isinstance(price, Decimal):
                    self._fail(channel, symbol, f'{side} price is {type(price).__name__}, expected Decimal')
                    break
                if price <= 0:
                    self._fail(channel, symbol, f'{side} price is {price}')
                    break
                total = sum(size.values()) if isinstance(size, dict) else size
                if total <= 0:
                    self._fail(channel, symbol, f'{side} size at {price} is {total}')
                    break

        sequence = getattr(book, 'sequence_number', None)
        if sequence is not None:
            key = (channel, symbol)
            previous = self._sequences.get(key)
            # venues coalesce updates and repeat a sequence number, so equality is expected
            if previous is not None and sequence < previous:
                self.sequence_resets += 1
                if book.delta is not None:
                    self._fail(channel, symbol, f'sequence went backwards on a delta: {previous} -> {sequence}')
            self._sequences[key] = sequence
