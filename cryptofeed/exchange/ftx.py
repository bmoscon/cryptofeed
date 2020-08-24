'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from time import time

import aiohttp
import pandas as pd
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import BID, ASK, BUY
from cryptofeed.defines import FTX as FTX_id
from cryptofeed.defines import FUNDING, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, SELL, TICKER, TRADES
from cryptofeed.feed import Feed, RestFeed
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class FTX(Feed):
    id = FTX_id

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://ftexchange.com/ws/', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)

    def __reset(self):
        self.l2_book = {}
        self.funding = {}
        self.open_interest = {}

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        for chan in self.channels if self.channels else self.config:
            if chan == FUNDING:
                asyncio.create_task(self._funding(self.pairs if self.pairs else self.config[chan]))
                continue
            if chan == OPEN_INTEREST:
                asyncio.create_task(self._open_interest(self.pairs if self.pairs else self.config[chan]))
                continue
            for pair in self.pairs if self.pairs else self.config[chan]:
                await websocket.send(json.dumps(
                    {
                        "channel": chan,
                        "market": pair,
                        "op": "subscribe"
                    }
                ))

    async def _open_interest(self, pairs: list):
        """
            {
              "success": true,
              "result": {
                "volume": 1000.23,
                "nextFundingRate": 0.00025,
                "nextFundingTime": "2019-03-29T03:00:00+00:00",
                "expirationPrice": 3992.1,
                "predictedExpirationPrice": 3993.6,
                "strikePrice": 8182.35,
                "openInterest": 21124.583
              }
            }
        """

        rate_limiter = 1  # don't fetch too many pairs too fast
        async with aiohttp.ClientSession() as session:
            while True:
                for pair in pairs:
                    # OI only for perp and futures, so check for / in pair name indicating spot
                    if '/' in pair:
                        continue
                    end_point = f"https://ftx.com/api/futures/{pair}/stats"
                    async with session.get(end_point) as response:
                        data = await response.text()
                        data = json.loads(data, parse_float=Decimal)
                        if 'result' in data:
                            oi = data['result']['openInterest']
                            if oi != self.open_interest.get(pair, None):
                                await self.callback(OPEN_INTEREST,
                                                    feed=self.id,
                                                    pair=pair,
                                                    open_interest=oi,
                                                    timestamp=None,
                                                    receipt_timestamp=time()
                                                    )
                                self.open_interest[pair] = oi
                                await asyncio.sleep(rate_limiter)
                wait_time = 60
                await asyncio.sleep(wait_time)

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
                    if '-PERP' not in pair:
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
            if bool(trade['liquidation']):
                await self.callback(LIQUIDATIONS,
                                    feed=self.id,
                                    pair=pair_exchange_to_std(msg['market']),
                                    side=BUY if trade['side'] == 'buy' else SELL,
                                    leaves_qty=Decimal(trade['size']),
                                    price=Decimal(trade['price']),
                                    order_id=None,
                                    timestamp=float(timestamp_normalize(self.id, trade['time'])),
                                    receipt_timestamp=timestamp
                                    )

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
        if 'type' in msg and msg['type'] == 'subscribed':
            return
        elif 'channel' in msg:
            if msg['channel'] == 'orderbook':
                await self._book(msg, timestamp)
            elif msg['channel'] == 'trades':
                await self._trade(msg, timestamp)
            elif msg['channel'] == 'ticker':
                await self._ticker(msg, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
