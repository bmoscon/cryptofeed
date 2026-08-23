'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict

import zmq
import zmq.asyncio
from cryptofeed import _json as json

from cryptofeed.backends.backend import BackendQueue, BackendBookCallback, BackendCallback


class ZMQCallback(BackendQueue):
    hand_off = True
    retryable_exceptions = (zmq.ZMQError,)

    def __init__(self, host='127.0.0.1', port=5555, none_to=None, numeric_type=float, key=None, dynamic_key=True, **kwargs):
        super().__init__(**kwargs)
        self.url = "tcp://{}:{}".format(host, port)
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.dynamic_key = dynamic_key
        self.con = None

    async def connect(self):
        if self.con is None or self.con.closed:
            self.con = zmq.asyncio.Context.instance().socket(zmq.PUB)
            self.con.connect(self.url)

    async def write_batch(self, batch: list):
        for update in batch:
            if self.dynamic_key:
                msg = f'{update["exchange"]}-{self.key}-{update["symbol"]} {json.dumps(update)}'
            else:
                msg = f'{self.key} {json.dumps(update)}'
            await self.con.send_string(msg)

    async def close(self):
        if self.con is not None:
            self.con.close()
            self.con = None


class TradeZMQ(ZMQCallback, BackendCallback):
    default_key = 'trades'


class TickerZMQ(ZMQCallback, BackendCallback):
    default_key = 'ticker'


class FundingZMQ(ZMQCallback, BackendCallback):
    default_key = 'funding'


class BookZMQ(ZMQCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


class OpenInterestZMQ(ZMQCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsZMQ(ZMQCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesZMQ(ZMQCallback, BackendCallback):
    default_key = 'candles'
