'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
import zlib

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, TICKER, L2_BOOK, OKCOIN
from cryptofeed.standards import pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class OKCoin(Feed):
    id = OKCOIN

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://real.okcoin.com:10442/ws/v3', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.book_depth = 200

    def __reset(self):
        self.l2_book = {}

    async def subscribe(self, websocket):
        self.__reset()
        if self.config:
            for chan in self.config:
                args = [f"{chan}:{pair}" for pair in self.config[chan]]
                await websocket.send(json.dumps({
                        "op": "subscribe",
                        "args": args
                    }))
        else:
            chans = [f"{chan}:{pair}" for chan in self.channels for pair in self.pairs]
            await websocket.send(json.dumps({
                                    "op": "subscribe",
                                    "args": chans
                                }))

    async def _ticker(self, msg):
        """
        {'table': 'spot/ticker', 'data': [{'instrument_id': 'BTC-USD', 'last': '3977.74', 'best_bid': '3977.08', 'best_ask': '3978.73', 'open_24h': '3978.21', 'high_24h': '3995.43', 'low_24h': '3961.02', 'base_volume_24h': '248.245', 'quote_volume_24h': '988112.225861', 'timestamp': '2019-03-22T22:26:34.019Z'}]}
        """
        for update in msg['data']:
            await self.callbacks[TICKER](feed=self.id,
                                         pair=update['instrument_id'],
                                         bid=Decimal(update['best_bid']),
                                         ask=Decimal(update['best_ask']))

    async def _trade(self, msg):
        """
        {'table': 'spot/trade', 'data': [{'instrument_id': 'BTC-USD', 'price': '3977.44', 'side': 'buy', 'size': '0.0096', 'timestamp': '2019-03-22T22:45:44.578Z', 'trade_id': '486519521'}]}
        """
        for trade in msg['data']:
            await self.callbacks[TRADES](
                feed=self.id,
                pair=pair_exchange_to_std(trade['instrument_id']),
                order_id=trade['trade_id'],
                side=BUY if trade['side'] == 'buy' else SELL,
                amount=Decimal(trade['size']),
                price=Decimal(trade['price']),
                timestamp=trade['timestamp']
            )

    async def _book(self, msg):
        if msg['action'] == 'partial':
            # snapshot
            for update in msg['data']:
                pair = pair_exchange_to_std(update['instrument_id'])
                self.l2_book[pair] = {
                    BID: sd({
                        Decimal(price) : Decimal(amount) for price, amount, _ in update['bids']
                    }),
                    ASK: sd({
                        Decimal(price) : Decimal(amount) for price, amount, _ in update['asks']
                    })
                }
                await self.book_callback(pair, L2_BOOK, True, None, update['timestamp'])
        else:
            # update
            for update in msg['data']:
                delta = {BID: [], ASK: []}
                pair = pair_exchange_to_std(update['instrument_id'])
                for side in ('bids', 'asks'):
                    s = BID if side == 'bids' else ASK
                    for price, amount, _ in update[side]:
                        price = Decimal(price)
                        amount = Decimal(amount)
                        if amount == 0:
                            delta[s].append((price, 0))
                            del self.l2_book[pair][s][price]
                        else:
                            delta[s].append((price, amount))
                            self.l2_book[pair][s][price] = amount
                await self.book_callback(pair, L2_BOOK, False, delta, update['timestamp'])

    async def message_handler(self, msg):
        # DEFLATE compression, no header
        msg = zlib.decompress(msg, -15)
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            if msg['event'] == 'error':
                LOG.error("%s: Error: %s", self.id, msg)
            elif msg['event'] == 'subscribe':
                pass
            else:
                LOG.warning("%s: Unhandled event %s", self.id, msg)
        elif 'table' in msg:
            if msg['table'] == 'spot/ticker':
                await self._ticker(msg)
            elif msg['table'] == 'spot/trade':
                await self._trade(msg)
            elif msg['table'] == 'spot/depth':
                await self._book(msg)
            else:
                LOG.warning("%s: Unhandled message %s", self.id, msg)
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)
