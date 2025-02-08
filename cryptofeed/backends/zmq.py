'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict

import zmq
import zmq.asyncio
from yapic import json

from cryptofeed.backends.backend import BackendQueue, BackendBookCallback, BackendCallback


class ZMQCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', port=5555, none_to=None, numeric_type=float, key=None, dynamic_key=True, **kwargs):
        self.url = "tcp://{}:{}".format(host, port)
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.dynamic_key = dynamic_key
        self.running = True

    async def writer(self):
        ctx = zmq.asyncio.Context.instance()
        con = ctx.socket(zmq.PUB)
        con.connect(self.url)
        while self.running:
            async with self.read_queue() as updates:
                for update in updates:
                    if self.dynamic_key:
                        update = f'{update["exchange"]}-{self.key}-{update["symbol"]} {json.dumps(update)}'
                    else:
                        update = f'{self.key} {json.dumps(update)}'
                    await con.send_string(update)


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


class BalancesZMQ(ZMQCallback, BackendCallback):
    default_key = 'balances'


class PositionsZMQ(ZMQCallback, BackendCallback):
    default_key = 'positions'


class OrderInfoZMQ(ZMQCallback, BackendCallback):
    default_key = 'order_info'


class FillsZMQ(ZMQCallback, BackendCallback):
    default_key = 'fills'


class TransactionsZMQ(ZMQCallback, BackendCallback):
    default_key = 'transactions'
