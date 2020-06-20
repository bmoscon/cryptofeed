'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
import aiohttp
import hmac
import time
import os
import yaml
import pandas as pd

from yapic import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed, RestFeed
from cryptofeed.defines import FTX as FTX_id
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, TICKER, L2_BOOK, FUNDING, FILLS
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class FTX(Feed):
    id = FTX_id

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://ftexchange.com/ws/', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.logged_in = False
        path = os.path.dirname(os.path.abspath(__file__))
        self.key_id, self.key_secret, self.key_passphrase = None, None, None
        config = "api_keys.yaml"

        try:
            with open(os.path.join(path, config), 'r') as fp:
                data = yaml.safe_load(fp)
                self.key_id = data['ftx']['key_id']
                self.key_secret = data['ftx']['key_secret']
        except (KeyError, FileNotFoundError, TypeError):
            pass

    def __reset(self):
        self.l2_book = {}
        self.funding = {}

    async def login(self, websocket=None):
        if self.logged_in:
            return
        self.logged_in = True
        ts = int(time.time() * 1000)
        signature = hmac.new(self.key_secret.encode(), f'{ts}websocket_login'.encode(), 'sha256').hexdigest()
        if websocket is not None:
            self.websocket = websocket
        await self.websocket.send(json.dumps(
            {
                "args": {
                    "key": self.key_id,
                    "sign": signature,
                    "time": ts
                },
                "op": "login"
            }
        ))

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        for chan in self.channels if self.channels else self.config:
            if chan == 'funding':
                asyncio.create_task(self._funding(self.pairs if self.pairs else self.config[chan]))
                continue
            for pair in self.pairs if self.pairs else self.config[chan]:
                await websocket.send(json.dumps(
                    {
                        "channel": chan,
                        "market": pair,
                        "op": "subscribe"
                    }
                ))

    async def unsubscribe(self, websocket):
        self.websocket = websocket
        for chan in self.channels if self.channels else self.config:
            for pair in self.pairs if self.pairs else self.config[chan]:
                await websocket.send(json.dumps(
                    {
                        "channel": chan,
                        "market": pair,
                        "op": "unsubscribe"
                    }
                ))

    async def _fills(self, msg: dict, timestamp: float):
        """
        example message:

        {'channel': 'fills', 'type': 'update', 'data': {'id': 109096206, 'market': 'BTC-MOVE-WK-0619',
        'future': 'BTC-MOVE-WK-0619', 'baseCurrency': None, 'quoteCurrency': None, 'type': 'order', 'side': 'sell',
        'price': Decimal('133.0'), 'size': Decimal('0.0001'), 'orderId': 6039056668,
        'time': datetime.datetime(2020, 6, 19, 15, 31, 15, 479586, tzinfo=datetime.timezone.utc), 'tradeId': 54158600,
        'feeRate': Decimal('0.000965'), 'fee': Decimal('0.0009030854920944018'), 'feeCurrency': 'USD',
        'liquidity': 'taker'}}
        """

        await self.callback(FILLS, feed=self.id,
                            pair=pair_exchange_to_std(msg['data']['market']),
                            side=BUY if msg['data']['side'] == 'buy' else SELL,
                            amount=Decimal(msg['data']['size']),
                            price=Decimal(msg['data']['price']),
                            fee=msg['data']['fee'],
                            fee_rate=msg['data']['feeRate'],
                            id=msg['data']['id'],
                            order_id=msg['data']['orderId'],
                            trade_id=msg['data']['tradeId'],
                            timestamp=float(timestamp_normalize(self.id, msg['data']['time'])),
                            liquidity=msg['data']['liquidity'],
                            type=msg['data']['type'],
                            receipt_timestamp=timestamp)

    async def _funding(self, pairs: list):
        """
            {
              "success": true,
              "result": [
                {
                  "future": "BTC-PERP",
                  "rate": 0.0025,
                  "time": "2019-06-02T08:00:00+00:00"
                }
              ]
            }
        """
        wait_time = len(pairs) / 30
        async with aiohttp.ClientSession() as session:
            while True:
                for pair in pairs:
                    if not '-PERP' in pair:
                        continue
                    async with session.get(f"https://ftx.com/api/funding_rates?future={pair}") as response:
                        data = await response.text()
                        data = json.loads(data, parse_float=Decimal)

                        last_update = self.funding.get(pair, None)
                        update = str(data['result'][0]['rate']) + str(data['result'][0]['time'])
                        if last_update and last_update == update:
                            continue
                        else:
                            self.funding[pair] = update

                        await self.callback(FUNDING, feed=self.id,
                                            pair=pair_exchange_to_std(data['result'][0]['future']),
                                            rate=data['result'][0]['rate'],
                                            timestamp=timestamp_normalize(self.id, data['result'][0]['time']))
                    await asyncio.sleep(wait_time)

    async def _trade(self, msg: dict, timestamp: float):
        """
        example message:

        {"channel": "trades", "market": "BTC-PERP", "type": "update", "data": [{"id": null, "price": 10738.75,
        "size": 0.3616, "side": "buy", "liquidation": false, "time": "2019-08-03T12:20:19.170586+00:00"}]}
        """
        for trade in msg['data']:
            await self.callback(TRADES, feed=self.id,
                                pair=pair_exchange_to_std(msg['market']),
                                side=BUY if trade['side'] == 'buy' else SELL,
                                amount=Decimal(trade['size']),
                                price=Decimal(trade['price']),
                                order_id=None,
                                timestamp=float(timestamp_normalize(self.id, trade['time'])),
                                receipt_timestamp=timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        example message:

        {"channel": "ticker", "market": "BTC/USD", "type": "update", "data": {"bid": 10717.5, "ask": 10719.0,
        "last": 10719.0, "time": 1564834587.1299787}}
        """
        await self.callback(TICKER, feed=self.id,
                            pair=pair_exchange_to_std(msg['market']),
                            bid=Decimal(msg['data']['bid'] if msg['data']['bid'] else 0.0),
                            ask=Decimal(msg['data']['ask'] if msg['data']['ask'] else 0.0),
                            timestamp=float(msg['data']['time']),
                            receipt_timestamp=timestamp)

    async def _book(self, msg: dict, timestamp: float):
        """
        example messages:

        snapshot:
        {"channel": "orderbook", "market": "BTC/USD", "type": "partial", "data": {"time": 1564834586.3382702,
        "checksum": 427503966, "bids": [[10717.5, 4.092], ...], "asks": [[10720.5, 15.3458], ...], "action": "partial"}}

        update:
        {"channel": "orderbook", "market": "BTC/USD", "type": "update", "data": {"time": 1564834587.1299787,
        "checksum": 3115602423, "bids": [], "asks": [[10719.0, 14.7461]], "action": "update"}}
        """
        if msg['type'] == 'partial':
            # snapshot
            pair = pair_exchange_to_std(msg['market'])
            self.l2_book[pair] = {
                BID: sd({
                    Decimal(price): Decimal(amount) for price, amount in msg['data']['bids']
                }),
                ASK: sd({
                    Decimal(price): Decimal(amount) for price, amount in msg['data']['asks']
                })
            }
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, float(msg['data']['time']), timestamp)
        else:
            # update
            delta = {BID: [], ASK: []}
            pair = pair_exchange_to_std(msg['market'])
            for side in ('bids', 'asks'):
                s = BID if side == 'bids' else ASK
                for price, amount in msg['data'][side]:
                    price = Decimal(price)
                    amount = Decimal(amount)
                    if amount == 0:
                        delta[s].append((price, 0))
                        del self.l2_book[pair][s][price]
                    else:
                        delta[s].append((price, amount))
                        self.l2_book[pair][s][price] = amount
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, float(msg['data']['time']), timestamp)

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if 'type' in msg and (msg['type'] == 'subscribed' or msg['type'] == 'unsubscribed'):
            return
        elif 'type' in msg and msg['type'] == 'error' and 'Not logged in' in msg['msg']:
            self.logged_in = False
            await self.login(None)
        elif 'type' in msg and msg['type'] == 'error' and 'Already logged in' in msg['msg']:
            return
        elif 'channel' in msg:
            if msg['channel'] == 'orderbook':
                await self._book(msg, timestamp)
            elif msg['channel'] == 'trades':
                await self._trade(msg, timestamp)
            elif msg['channel'] == 'ticker':
                await self._ticker(msg, timestamp)
            elif msg['channel'] == 'fills':
                await self._fills(msg, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
