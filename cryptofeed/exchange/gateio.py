'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from decimal import Decimal

import requests
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import BID, ASK, BUY, GATEIO, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Gateio(Feed):
    id = GATEIO

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://ws.gate.io/v3/', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _ticker(self, msg: dict, timestamp: float):
        """
        missing bid/ask so not useable

        {
            'method': 'ticker.update',
            'params': [
                'BTC_USDT',
                {
                    'period': 86400,
                    'open': '11836.29',
                    'close': '11451.58',
                    'high': '11872.54',
                    'low': '11380',
                    'last': '11451.58',
                    'change': '-3.25',
                    'quoteVolume': '1360.8451746822',
                    'baseVolume': '15905013.385494827953'
                }
            ],
            'id': None
        }
        """
        pass

    async def _trades(self, msg: dict, timestamp: float):
        """
        {
            'method': 'trades.update',
            'params': [
                'BTC_USDT',
                [
                    {
                        'id': 274655681,
                        'time': Decimal('1598060303.5162649'),
                        'price': '11449.69',
                        'amount': '0.0003',
                        'type': 'buy'
                    },
                    {
                        'id': 274655680,
                        'time': Decimal('1598060303.5160251'),
                        'price': '11449.3',
                        'amount': '0.0012',
                        'type': 'buy'
                    }
                ]
            ],
            'id': None
        }
        """
        symbol, trades = msg['params']
        symbol = pair_exchange_to_std(symbol)
        # list of trades appears to be in most recent to oldest, to reverse to deliver them in chronological order
        for trade in reversed(trades):
            side = BUY if trade['type'] == 'buy' else SELL
            amount = Decimal(trade['amount'])
            price = Decimal(trade['price'])
            ts = float(trade['time'])
            order_id = trade['id']
            await self.callback(TRADES, feed=self.id,
                                pair=symbol,
                                side=side,
                                amount=amount,
                                price=price,
                                timestamp=ts,
                                receipt_timestamp=timestamp,
                                order_id=order_id)

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if "error" in msg:
            if msg['error'] is None:
                pass
            else:
                LOG.warning("%s: Error received from exchange - %s", self.id, msg)
        elif 'method' in msg:
            if msg['method'] == 'trades.update':
                await self._trades(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        client_id = 0
        for chan in self.channels if self.channels else self.config:
            pairs = self.pairs if self.pairs else self.config[chan]
            client_id += 1
            await websocket.send(json.dumps(
                {
                    "method": chan,
                    "params": pairs,
                    "id": client_id
                }
            ))
