'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import Counter


def _trade_key(trade):
    # trade id, or the trade as a tuple if no trade id provided
    # ids compare by length first
    if trade.id is not None:
        return (0, len(trade.id), trade.id)
    return (1, trade.side, trade.price, trade.amount)


def _symbol(trade):
    return trade.symbol


def _stream(candle):
    return (candle.symbol, candle.interval)


def _start(candle):
    return candle.start


def _group(rows, stream, extra=None) -> dict:
    groups = {} if extra is None else {extra: []}
    for row in rows:
        groups.setdefault(stream(row), []).append(row)
    return groups


class TradeWatermark:
    # at a high level, this ensures that a feed delivers every trade once and only once, and in time ascending order
    def __init__(self, history: bool = False, key=None):
        self.history = history
        self.key = key
        self._marks = {}
        self.pending = set()

    def get(self, symbol):
        mark = self._marks.get(symbol)
        return None if mark is None else mark[0]

    def batch(self, trades, symbol=None) -> list:
        key = self.key or _trade_key
        out = []

        for sym, rows in _group(trades, _symbol, symbol).items():
            rows.sort(key=lambda t: (t.timestamp, key(t)))
            mark = self._marks.get(sym)

            if mark is None:
                self._marks[sym] = [None, Counter()]
                fresh = rows if self.history else []
                seen = rows
            else:
                fresh = seen = self._newer(mark, rows, key)
            for trade in seen:
                self._note(sym, trade, key)
            out.extend(fresh)

        return out

    def live(self, trades, sort=False) -> list:
        key = self.key or _trade_key
        trades = sorted(trades, key=lambda t: (t.timestamp, key(t))) if sort else list(trades)
        for trade in trades:
            self._note(trade.symbol, trade, key)
        return trades

    def expect(self, symbols):
        self.pending.update(symbols)

    def frame(self, trades, symbol) -> list:
        if symbol in self.pending:
            self.pending.discard(symbol)
            return self.batch(trades, symbol=symbol)
        return self.live(trades)

    @staticmethod
    def _newer(mark, rows, key) -> list:
        ts, keys = mark
        if ts is None:
            return rows

        budget = keys.copy()
        fresh = []
        for trade in rows:
            if trade.timestamp < ts:
                continue
            if trade.timestamp == ts:
                row_key = key(trade)
                if budget[row_key] > 0:
                    budget[row_key] -= 1
                    continue
            fresh.append(trade)

        return fresh

    def _note(self, symbol, trade, key):
        ts = trade.timestamp
        mark = self._marks.get(symbol)
        if mark is None or mark[0] is None or ts > mark[0]:
            self._marks[symbol] = [ts, Counter((key(trade),))]
        elif ts == mark[0]:
            mark[1][key(trade)] += 1


class CandleWatermark:
    # at a high level, this ensures that a feed delivers every candle
    # once and only once, and in time ascending order
    def __init__(self, history: bool = False):
        self.history = history
        self._marks = {}

    def get(self, symbol, interval):
        return self._marks.get((symbol, interval))

    def batch(self, candles, symbol=None, interval=None) -> list:
        out = []
        for stream, rows in _group(candles, _stream, None if symbol is None else (symbol, interval)).items():
            rows.sort(key=_start)
            first = stream not in self._marks
            mark = self._marks.get(stream)

            for candle in rows:
                if candle.closed and (mark is None or candle.start > mark):
                    if self.history or not first:
                        out.append(candle)
                    mark = candle.start
            self._marks[stream] = mark

            if rows and not rows[-1].closed and (mark is None or rows[-1].start > mark):
                out.append(rows[-1])

        return out

    def live(self, candles) -> list:
        out = []
        for candle in sorted(candles, key=_start):
            stream = (candle.symbol, candle.interval)
            mark = self._marks.get(stream)

            if mark is not None and candle.start <= mark:
                continue
            if candle.closed:
                self._marks[stream] = candle.start

            out.append(candle)

        return out
