'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json

import zmq
import zmq.asyncio

from cryptofeed.backends.backend import BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback, BackendTickerCallback, BackendTradeCallback, BackendOpenInterestCallback


class ZMQCallback:
    def __init__(self, host='127.0.0.1', port=5555, numeric_type=float, key=None, dynamic_key=True, **kwargs):
        url = "tcp://{}:{}".format(host, port)
        ctx = zmq.asyncio.Context.instance()
        self.con = ctx.socket(zmq.PUB)
        self.con.connect(url)
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.dynamic_key = dynamic_key

    async def write(self, feed, pair, timestamp, data):
        if self.dynamic_key:
            await self.con.send_string(f'{feed}-{self.key}-{pair} {json.dumps(data)}')
        else:
            await self.con.send_string(f'{self.key} {json.dumps(data)}')


class TradeZMQ(ZMQCallback, BackendTradeCallback):
    default_key = 'trades'


class TickerZMQ(ZMQCallback, BackendTickerCallback):
    default_key = 'ticker'


class FundingZMQ(ZMQCallback, BackendFundingCallback):
    default_key = 'funding'


class BookZMQ(ZMQCallback, BackendBookCallback):
    default_key = 'book'


class BookDeltaZMQ(ZMQCallback, BackendBookDeltaCallback):
    default_key = 'book'


class OpenInterestZMQ(ZMQCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'
