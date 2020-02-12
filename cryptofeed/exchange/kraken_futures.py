'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
import requests
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, TICKER, FUNDING, L2_BOOK, KRAKEN_FUTURES, OPEN_INTEREST
from cryptofeed.standards import timestamp_normalize

LOG = logging.getLogger('feedhandler')


class KrakenFutures(Feed):
    id = KRAKEN_FUTURES

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://futures.kraken.com/ws/v1', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)

        instruments = self.get_instruments()
        if self.config:
            config_instruments = list(self.config.values())
            self.pairs = [
                pair for inner in config_instruments for pair in inner]

        for pair in self.pairs:
            if pair not in instruments:
                raise ValueError(f"{pair} is not active on {self.id}")

        self.__reset()

    def __reset(self):
        self.open_interest = {}
        self.l2_book = {}

    @staticmethod
    def get_instruments():
        r = requests.get('https://futures.kraken.com/derivatives/api/v3/instruments').json()
        return {e['symbol'].upper(): e['symbol'].upper() for e in r['instruments']}

    async def subscribe(self, websocket):
        self.__reset()
        for chan in self.channels if self.channels else self.config:
            await websocket.send(json.dumps(
                {
                    "event": "subscribe",
                    "feed": chan,
                    "product_ids": self.pairs if not self.config else list(self.config[chan])
                }
            ))

    async def _trade(self, msg: dict, pair: str):
        """
        {
            "feed": "trade",
            "product_id": "PI_XBTUSD",
            "uid": "b5a1c239-7987-4207-96bf-02355a3263cf",
            "side": "sell",
            "type": "fill",
            "seq": 85423,
            "time": 1565342712903,
            "qty": 1135.0,
            "price": 11735.0
        }
        """
        await self.callback(TRADES, feed=self.id,
                            pair=pair,
                            side=BUY if msg['side'] == 'buy' else SELL,
                            amount=Decimal(msg['qty']),
                            price=Decimal(msg['price']),
                            order_id=msg['uid'],
                            timestamp=timestamp_normalize(self.id, msg['time']))

    async def _ticker(self, msg: dict, pair: str, timestamp: float):
        """
        {
            "feed": "ticker_lite",
            "product_id": "PI_XBTUSD",
            "bid": 11726.5,
            "ask": 11732.5,
            "change": 0.0,
            "premium": -0.1,
            "volume": "7.0541503E7",
            "tag": "perpetual",
            "pair": "XBT:USD",
            "dtm": -18117,
            "maturityTime": 0
        }
        """
        await self.callback(TICKER, feed=self.id, pair=pair, bid=msg['bid'], ask=msg['ask'], timestamp=timestamp)

    async def _book_snapshot(self, msg: dict, pair: str, timestamp: float):
        """
        {
            "feed": "book_snapshot",
            "product_id": "PI_XBTUSD",
            "timestamp": 1565342712774,
            "seq": 30007298,
            "bids": [
                {
                    "price": 11735.0,
                    "qty": 50000.0
                },
                ...
            ],
            "asks": [
                {
                    "price": 11739.0,
                    "qty": 47410.0
                },
                ...
            ],
            "tickSize": null
        }
        """
        self.l2_book[pair] = {
            BID: sd({Decimal(update['price']): Decimal(update['qty']) for update in msg['bids']}),
            ASK: sd({Decimal(update['price']): Decimal(update['qty']) for update in msg['asks']})
        }
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp)

    async def _book(self, msg: dict, pair: str, timestamp: float):
        """
        Message is received for every book update:
        {
            "feed": "book",
            "product_id": "PI_XBTUSD",
            "side": "sell",
            "seq": 30007489,
            "price": 11741.5,
            "qty": 10000.0,
            "timestamp": 1565342713929
        }
        """
        delta = {BID: [], ASK: []}
        s = BID if msg['side'] == 'buy' else ASK
        price = Decimal(msg['price'])
        amount = Decimal(msg['qty'])

        if amount == 0:
            delta[s].append((price, 0))
            del self.l2_book[pair][s][price]
        else:
            delta[s].append((price, amount))
            self.l2_book[pair][s][price] = amount

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp)

    async def _funding(self, msg: dict, pair: str):
        if msg['tag'] == 'perpetual':
            await self.callback(FUNDING,
                                feed=self.id,
                                pair=pair,
                                timestamp=timestamp_normalize(self.id, msg['time']),
                                tag=msg['tag'],
                                rate=msg['funding_rate'],
                                rate_prediction=msg.get('funding_rate_prediction', None),
                                relative_rate=msg['relative_funding_rate'],
                                relative_rate_prediction=msg.get('relative_funding_rate_prediction', None),
                                next_rate_timestamp=timestamp_normalize(self.id, msg['next_funding_rate_time']))
        else:
            await self.callback(FUNDING,
                                feed=self.id,
                                pair=pair,
                                timestamp=timestamp_normalize(self.id, msg['time']),
                                tag=msg['tag'],
                                premium=msg['premium'],
                                maturity_timestamp=timestamp_normalize(self.id, msg['maturityTime']))

        oi = msg['openInterest']
        if pair in self.open_interest and oi == self.open_interest[pair]:
            return
        self.open_interest[pair] = oi
        await self.callback(OPEN_INTEREST,
                            feed=self.id,
                            pair=pair,
                            open_interest=msg['openInterest'],
                            timestamp=timestamp_normalize(self.id, msg['time'])
                        )

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            if msg['event'] == 'info':
                return
            elif msg['event'] == 'subscribed':
                return
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            if msg['feed'] == 'trade':
                await self._trade(msg, msg['product_id'])
            elif msg['feed'] == 'trade_snapshot':
                return
            elif msg['feed'] == 'ticker_lite':
                await self._ticker(msg, msg['product_id'], timestamp)
            elif msg['feed'] == 'ticker':
                await self._funding(msg, msg['product_id'])
            elif msg['feed'] == 'book_snapshot':
                await self._book_snapshot(msg, msg['product_id'], timestamp)
            elif msg['feed'] == 'book':
                await self._book(msg, msg['product_id'], timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
