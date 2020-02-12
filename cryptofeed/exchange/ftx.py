'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import FTX as FTX_id
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, TICKER, L2_BOOK
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

    async def _trade(self, msg):
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
                                timestamp=float(timestamp_normalize(self.id, trade['time'])))

    async def _ticker(self, msg):
        """
        example message:

        {"channel": "ticker", "market": "BTC/USD", "type": "update", "data": {"bid": 10717.5, "ask": 10719.0,
        "last": 10719.0, "time": 1564834587.1299787}}
        """
        await self.callback(TICKER, feed=self.id,
                            pair=pair_exchange_to_std(msg['market']),
                            bid=Decimal(msg['data']['bid'] if msg['data']['bid'] else 0.0),
                            ask=Decimal(msg['data']['ask'] if msg['data']['ask'] else 0.0),
                            timestamp=float(msg['data']['time']))

    async def _book(self, msg: dict):
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
                    Decimal(price) : Decimal(amount) for price, amount in msg['data']['bids']
                }),
                ASK: sd({
                    Decimal(price) : Decimal(amount) for price, amount in msg['data']['asks']
                })
            }
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, float(msg['data']['time']))
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
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, float(msg['data']['time']))

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if 'type' in msg and msg['type'] == 'subscribed':
            return
        elif 'channel' in msg:
            if msg['channel'] == 'orderbook':
                await self._book(msg)
            elif msg['channel'] == 'trades':
                await self._trade(msg)
            elif msg['channel'] == 'ticker':
                await self._ticker(msg)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
