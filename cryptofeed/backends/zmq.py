'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import zmq
import zmq.asyncio
from yapic import json

from cryptofeed.backends.backend import (BackendCandlesCallback, BackendQueue, BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendFuturesIndexCallback, BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, DeribitBackendBookCallback, DeribitBackendTickerCallback, DeribitBackendTradeCallback,
                                         BackendVolumeCallback, BackendUserBalanceCallback, BackendUserPositionCallback,
                                         BackendUserFillCallback, BackendUserOrderCallback)
from cryptofeed.defines import FUTURES_INDEX, TRADES, USER_FILLS, VOLUME, USER_BALANCE, ORDER_INFO, USER_POSITION


class ZMQCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', port=5555, numeric_type=float, key=None, dynamic_key=True, **kwargs):
        url = "tcp://{}:{}".format(host, port)
        ctx = zmq.asyncio.Context.instance()
        self.con = ctx.socket(zmq.PUB)
        self.con.bind(url)
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.dynamic_key = dynamic_key

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        if self.dynamic_key:
            await self.queue.put(f'{feed}-{self.key}-{symbol} {json.dumps(data)}')
        else:
            await self.queue.put(f'{self.key} {json.dumps(data)}')

    async def writer(self):
        while True:
            async with self.read_queue() as update:
                await self.con.send_string(update)


class TradeZMQ(ZMQCallback, BackendTradeCallback):
    default_key = 'trades'


class DeribitTradeZMQ(ZMQCallback, DeribitBackendTradeCallback):
    default_key = TRADES


class TickerZMQ(ZMQCallback, BackendTickerCallback):
    default_key = 'ticker'


class DeribitTickerZMQ(ZMQCallback, DeribitBackendTickerCallback):
    default_key = 'tickers'


class FundingZMQ(ZMQCallback, BackendFundingCallback):
    default_key = 'funding'


class BookZMQ(ZMQCallback, BackendBookCallback):
    default_key = 'book'


class DeribitBookZMQ(ZMQCallback, DeribitBackendBookCallback):
    default_key = 'books'


class BookDeltaZMQ(ZMQCallback, BackendBookDeltaCallback):
    default_key = 'book'


class OpenInterestZMQ(ZMQCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsZMQ(ZMQCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class FuturesIndexZMQ(ZMQCallback, BackendFuturesIndexCallback):
    default_key = FUTURES_INDEX


class VolumeZMQ(ZMQCallback, BackendVolumeCallback):
    default_key = VOLUME


class CandlesZMQ(ZMQCallback, BackendCandlesCallback):
    default_key = 'candles'


class UserBalanceZMQ(ZMQCallback, BackendUserBalanceCallback):
    default_key = USER_BALANCE


class UserPositionZMQ(ZMQCallback, BackendUserPositionCallback):
    default_key = USER_POSITION


class UserFillZMQ(ZMQCallback, BackendUserFillCallback):
    default_key = USER_FILLS


class OrderInfoZMQ(ZMQCallback, BackendUserOrderCallback):
    default_key = ORDER_INFO