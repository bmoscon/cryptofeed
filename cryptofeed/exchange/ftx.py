'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
import aiohttp
import pandas as pd

from yapic import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed, RestFeed
from cryptofeed.defines import FTX as FTX_id
from cryptofeed.defines import FTX_REST as FTX_REST_id
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, TICKER, L2_BOOK, FUNDING
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')

class FTX(Feed):
    id = FTX_id

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://ftexchange.com/ws/', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)

    def __reset(self):
        self.l2_book = {}

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        for chan in self.channels if self.channels else self.config:
            for pair in self.pairs if self.pairs else self.config[chan]:
                await websocket.send(json.dumps(
                    {
                        "channel": chan,
                        "market": pair,
                        "op": "subscribe"
                    }
                ))

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


class FTXRest(RestFeed):
    id = FTX_REST_id

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__('https://ftx.com/api/', pairs=pairs, channels=channels, config=config,
                         callbacks=callbacks, **kwargs)
        self.funding_fetched = False


    def __reset(self):
        self.last_trade_update = {}

    async def _trades(self, session, pair):
        raise NotImplementedError

    async def _ticker(self, session, pair):
        raise NotImplementedError

    async def _funding(self, session, pair):
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
        async with session.get(f"{self.address}funding_rates?future={pair}") as response:
            data = await response.json()
            await self.callback(FUNDING, feed=self.id,
                                pair=pair_exchange_to_std(data['result'][0]['future']),
                                rate=data['result'][0]['rate'],
                                timestamp=timestamp_normalize(self.id, data['result'][0]['time']))

    async def _book(self, session, pair):
        raise NotImplemented

    async def subscribe(self):
        self.__reset()
        return

    async def message_handler(self):
        async def handle(session, pair, chan):
            if chan == TRADES:
                await self._trades(session, pair)
            elif chan == TICKER:
                await self._ticker(session, pair)
            elif chan == L2_BOOK:
                await self._book(session, pair)
            elif chan == FUNDING:
                await self._funding(session, pair)
            # We can do 15 requests a second
            await asyncio.sleep(0.07)

        async with aiohttp.ClientSession() as session:
            # date in Timestamp constructor is dummy, but needed by Pandas. Current minute is stored
            minute = pd.Timestamp(2016, 1, 1, 12, 25, 16, 28).now().minute
            if minute == 0 and not self.funding_fetched:
                # because funding will only be paid every hour, it doesn't make sense to
                # fetch funding every second or less

                if self.config:
                    for chan in self.config:
                        for pair in self.config[chan]:
                            await handle(session, pair, chan)
                else:
                    for chan in self.channels:
                        for pair in self.pairs:
                            await handle(session, pair, chan)
                self.funding_fetched = True
            elif minute != 0:
                self.funding_fetched = False
            else:
                pass


class FTXFeed(object):
    def __init__(self, pairs, channels, callbacks, config=None, **kwargs):
        self.rest_api = None
        index = -1
        i = 0
        for chan in channels if channels else config:
            if chan == 'funding':
                if kwargs['feed_handler']:
                    kwargs['feed_handler'].add_feed(FTXRest(pairs=pairs, channels=[FUNDING], callbacks=callbacks))
                index = i
            i += 1
        # now remove the funding feed, because it shouldn't be added to the websocket
        # also remove belonging callback and kwarg containg the feed_handler
        if index > -1:
            channels.pop(index)
            callbacks.pop('funding')
        kwargs['feed_handler'].add_feed(FTX(pairs=pairs, channels=channels, callbacks=callbacks))
