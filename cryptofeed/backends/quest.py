'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed import _json as json

from cryptofeed.backends._line_protocol import QUESTDB, TimestampMicros, encode
from cryptofeed.backends.backend import BackendCallback
from cryptofeed.backends.http import HTTPCallback


LOG = logging.getLogger(__name__)


class QuestCallback(HTTPCallback):
    def __init__(self, host='127.0.0.1', port=9000, key=None, **kwargs):
        super().__init__(f'http://{host}:{port}/write?precision=n', **kwargs)
        self.key = key if key else self.default_key
        self.numeric_type = float
        self.none_to = None

    def _tags(self, data: dict) -> dict:
        tags = {'symbol': data['symbol']}
        if 'interval' in data:
            tags['interval'] = data['interval']
        return tags

    def _fields(self, data: dict) -> dict:
        fields = {key: value for key, value in data.items() if key not in ('exchange', 'symbol', 'interval', 'timestamp', 'receipt_timestamp')}
        fields['receipt_timestamp'] = TimestampMicros(int(data['receipt_timestamp'] * 1_000_000))
        return fields

    def _encode(self, data: dict) -> str:
        timestamp = data['timestamp']
        timestamp_ns = int(timestamp * 1_000_000_000) if timestamp is not None else int(data['receipt_timestamp'] * 1_000_000) * 1000
        return encode(f'{self.key}-{data["exchange"]}', self._tags(data), self._fields(data), timestamp_ns, dialect=QUESTDB)

    def _rejected_line(self, body: str, lines: list):
        try:
            line = json.loads(body).get('line')
        except Exception:
            return None
        return line - 1 if isinstance(line, int) else None


class TradeQuest(QuestCallback, BackendCallback):
    default_key = 'trades'

    def _tags(self, data: dict) -> dict:
        return {'symbol': data['symbol'], 'side': data['side'], 'type': data['type']}

    def _fields(self, data: dict) -> dict:
        return {'price': data['price'], 'amount': data['amount'], 'id': data['id'], 'receipt_timestamp': TimestampMicros(int(data['receipt_timestamp'] * 1_000_000))}


class FundingQuest(QuestCallback, BackendCallback):
    default_key = 'funding'


class BookQuest(QuestCallback):
    default_key = 'book'

    def __init__(self, *args, depth=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = depth

    async def __call__(self, book, receipt_timestamp: float):
        data = {'exchange': book.exchange, 'symbol': book.symbol, 'timestamp': book.timestamp, 'receipt_timestamp': receipt_timestamp}
        levels = 0

        for side, side_book in (('bid', book.book.bids), ('ask', book.book.asks)):
            for i in range(min(self.depth, len(side_book))):
                price, size = side_book.index(i)
                data[f'{side}_{i}_price'] = price
                data[f'{side}_{i}_size'] = size
                levels += 1
        if not levels:
            return
        await self.write(data)


class TickerQuest(QuestCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestQuest(QuestCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsQuest(QuestCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesQuest(QuestCallback, BackendCallback):
    default_key = 'candles'
