'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.backends.backend import BackendCallback
from cryptofeed.backends.socket import SocketCallback


LOG = logging.getLogger('feedhandler')


class QuestCallback(SocketCallback):
    def __init__(self, host='127.0.0.1', port=9009, key=None, **kwargs):
        super().__init__(f"tcp://{host}", port=port, **kwargs)
        self.key = key if key else self.default_key
        self.numeric_type = float
        self.none_to = None
        self.running = True

    async def writer(self):
        while self.running:
            await self.connect()
            async with self.read_queue() as updates:
                update = "\n".join(updates) + "\n"
                self.conn.write(update.encode())

    async def write(self, data):
        d = self.format(data)
        timestamp = data["timestamp"]
        received_timestamp_int = int(data["receipt_timestamp"] * 1_000_000)
        timestamp_int = int(timestamp * 1_000_000_000) if timestamp is not None else received_timestamp_int * 1000
        update = f'{self.key}-{data["exchange"]},symbol={data["symbol"]} {d},receipt_timestamp={received_timestamp_int}t {timestamp_int}'
        await self.queue.put(update)

    def format(self, data):
        ret = []
        for key, value in data.items():
            if key in {'timestamp', 'exchange', 'symbol', 'receipt_timestamp'}:
                continue
            if isinstance(value, str):
                ret.append(f'{key}="{value}"')
            else:
                ret.append(f'{key}={value}')
        return ','.join(ret)


class TradeQuest(QuestCallback, BackendCallback):
    default_key = 'trades'

    async def write(self, data):
        timestamp = data["timestamp"]
        received_timestamp_int = int(data["receipt_timestamp"] * 1_000_000)
        id_field = f'id={data["id"]}i,' if data["id"] is not None else ''
        timestamp_int = int(timestamp * 1_000_000_000) if timestamp is not None else received_timestamp_int * 1000
        update = (
            f'{self.key}-{data["exchange"]},symbol={data["symbol"]},side={data["side"]},type={data["type"]} '
            f'price={data["price"]},amount={data["amount"]},{id_field}receipt_timestamp={received_timestamp_int}t {timestamp_int}'
        )
        await self.queue.put(update)


class FundingQuest(QuestCallback, BackendCallback):
    default_key = 'funding'


class BookQuest(QuestCallback):
    default_key = 'book'

    def __init__(self, *args, depth=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = depth

    async def __call__(self, book, receipt_timestamp: float):
        vals = ','.join([f"bid_{i}_price={book.book.bids.index(i)[0]},bid_{i}_size={book.book.bids.index(i)[1]}" for i in range(self.depth)] + [f"ask_{i}_price={book.book.asks.index(i)[0]},ask_{i}_size={book.book.asks.index(i)[1]}" for i in range(self.depth)])
        timestamp = book.timestamp
        receipt_timestamp_int = int(receipt_timestamp * 1_000_000)
        timestamp_int = int(timestamp * 1_000_000_000) if timestamp is not None else receipt_timestamp_int * 1000
        update = f'{self.key}-{book.exchange},symbol={book.symbol} {vals},receipt_timestamp={receipt_timestamp_int}t {timestamp_int}'
        await self.queue.put(update)


class TickerQuest(QuestCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestQuest(QuestCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsQuest(QuestCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesQuest(QuestCallback, BackendCallback):
    default_key = 'candles'

    async def write(self, data):
        timestamp = data["timestamp"]
        timestamp_str = f',timestamp={int(timestamp * 1_000_000_000)}i' if timestamp is not None else ''
        trades = f',trades={data["trades"]},' if data['trades'] else ','
        update = f'{self.key}-{data["exchange"]},symbol={data["symbol"]},interval={data["interval"]} start={data["start"]},stop={data["stop"]}{trades}open={data["open"]},close={data["close"]},high={data["high"]},low={data["low"]},volume={data["volume"]}{timestamp_str},receipt_timestamp={int(data["receipt_timestamp"]) * 1_000_000}t {int(data["receipt_timestamp"] * 1_000_000_000)}'
        await self.queue.put(update)


class OrderInfoQuest(QuestCallback, BackendCallback):
    default_key = 'order_info'


class TransactionsQuest(QuestCallback, BackendCallback):
    default_key = 'transactions'


class BalancesQuest(QuestCallback, BackendCallback):
    default_key = 'balances'


class FillsQuest(QuestCallback, BackendCallback):
    default_key = 'fills'
