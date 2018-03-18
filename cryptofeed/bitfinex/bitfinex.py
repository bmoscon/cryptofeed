'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import TICKER, TRADES, L3_BOOK, BID, ASK, L2_BOOK
from cryptofeed.exchanges import BITFINEX
from cryptofeed.standards import pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Bitfinex(Feed):
    id = BITFINEX

    def __init__(self, pairs=None, channels=None, callbacks=None):
        super().__init__('wss://api.bitfinex.com/ws/2', pairs, channels, callbacks)
        '''
        maps channel id (int) to a dict of
           symbol: channel's currency
           channel: channel name
           handler: the handler for this channel type
        '''
        self.channel_map = {}
        self.order_map = {}

    async def _ticker(self, msg):
        chan_id = msg[0]
        if msg[1] == 'hb':
            # ignore heartbeats
            pass
        else:
            # bid, bid_size, ask, ask_size, daily_change, daily_change_percent,
            # last_price, volume, high, low
            bid, _, ask, _, _, _, _, _, _, _ = msg[1]
            pair = self.channel_map[chan_id]['symbol']
            pair = pair_exchange_to_std(pair)
            await self.callbacks[TICKER](feed=self.id,
                                         pair=pair,
                                         bid=Decimal(bid),
                                         ask=Decimal(ask))

    async def _trades(self, msg):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)
        async def _trade_update(trade):
            # trade id, timestamp, amount, price
            _, _, amount, price = trade
            if amount < 0:
                side = ASK
            else:
                side = BID
            amount = abs(amount)
            await self.callbacks[TRADES](feed=self.id,
                                         pair=pair,
                                         side=side,
                                         amount=Decimal(amount),
                                         price=Decimal(price))

        if isinstance(msg[1], list):
            # snapshot
            for trade_update in msg[1]:
                await _trade_update(trade_update)
        else:
            # update
            if msg[1] == 'te':
                await _trade_update(msg[2])
            elif msg[1] == 'tu':
                # ignore trade updates
                pass
            elif msg[1] == 'hb':
                # ignore heartbeats
                pass
            else:
                LOG.warning("{} - Unexpected trade message {}".format(self.id, msg))

    async def _book(self, msg):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)

        if isinstance(msg[1], list):
            if isinstance(msg[1][0], list):
                # snapshot so clear book
                self.l2_book[pair] = {BID: sd(), ASK: sd()}
                for update in msg[1]:
                    price, _, amount = [Decimal(x) for x in update]
                    if amount > 0:
                        side = BID
                    else:
                        side = ASK
                        amount = abs(amount)
                    self.l2_book[pair][side][price] = amount
            else:
                # book update
                price, count, amount = [Decimal(x) for x in msg[1]]

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = abs(amount)

                if count > 0:
                    # change at price level
                    self.l2_book[pair][side][price] = amount
                else:
                    # remove price level
                    del self.l2_book[pair][side][price]
        elif msg[1] == 'hb':
            pass
        else:
            LOG.warning("{} - Unexpected book msg {}".format(self.id, msg))
        
        if L3_BOOK in self.channels:
            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.l2_book[pair])
        else:
            await self.callbacks[L2_BOOK](feed=self.id, pair=pair, book=self.l2_book[pair])


    async def _raw_book(self, msg):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)

        if isinstance(msg[1], list):
            if isinstance(msg[1][0], list):
                # snapshot so clear book
                self.l2_book[pair] = {BID: sd(), ASK: sd()}
                for update in msg[1]:
                    order_id, price, amount = update
                    price = Decimal(price)
                    amount = Decimal(amount)

                    if amount > 0:
                        side = BID
                    else:
                        side = ASK
                        amount = abs(amount)

                    if price not in self.l2_book[pair][side]:
                        self.l2_book[pair][side][price] = amount
                        self.order_map[order_id] = {'price': price, 'amount': amount, 'side': side}
                    else:
                        self.l2_book[pair][side][price]
                        self.l2_book[pair][side][price] += amount
                        self.order_map[order_id] = {'price': price, 'amount': amount, 'side': side}
            else:
                # book update
                order_id, price, amount = [Decimal(x) for x in msg[1]]

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = abs(amount)

                if price == 0:
                    price = self.order_map[order_id]['price']
                    self.l2_book[pair][side][price] -= self.order_map[order_id]['amount']
                    if self.l2_book[pair][side][price] == 0:
                        del self.l2_book[pair][side][price]
                    del self.order_map[order_id]
                else:
                    self.order_map[order_id] = {'price': price, 'amount': amount, 'side': side}
                    if price in self.l2_book[pair][side]:
                        self.l2_book[pair][side][price]
                        self.l2_book[pair][side][price] += amount
                    else:
                        self.l2_book[pair][side][price] = amount
        elif msg[1] == 'hb':
            pass
        else:
            LOG.warning("{} - Unexpected book msg {}".format(self.id, msg))
        
        if L3_BOOK in self.standardized_channels:
            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.l2_book[pair])
        else:
            await self.callbacks[L2_BOOK](feed=self.id, pair=pair, book=self.l2_book[pair])        

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if isinstance(msg, list):
            chan_id = msg[0]
            if chan_id in self.channel_map:
                await self.channel_map[chan_id]['handler'](msg)
            else:
                LOG.warning("{} - Unexpected message on unregistered channel {}".format(self.id, msg))
        elif 'event' in msg and msg['event'] == 'error':
            LOG.error("{} - Error message from exchange: {}".format(self.id, msg['msg']))
        elif 'chanId' in msg and 'symbol' in msg:
            handler = None
            if msg['channel'] == 'ticker':
                handler = self._ticker
            elif msg['channel'] == 'trades':
                handler = self._trades
            elif msg['channel'] == 'book':
                if msg['prec'] == 'R0':
                    handler = self._raw_book
                else:
                    handler = self._book
            else:
                LOG.warning('{} - Invalid message type {}'.format(self.id, msg))
                return
            self.channel_map[msg['chanId']] = {'symbol': msg['symbol'],
                                               'channel': msg['channel'],
                                               'handler': handler}

    async def subscribe(self, websocket):
        for channel in self.channels:
            for pair in self.pairs:
                message = {'event': 'subscribe',
                           'channel': channel,
                           'symbol': pair
                          }
                if 'book' in channel:
                    parts = channel.split('-')
                    if len(parts) != 1:
                        message['channel'] = 'book'
                        try:
                            message['prec'] = parts[1]
                            message['freq'] = parts[2]
                            message['len'] = parts[3]
                        except IndexError:
                            # any non specified params will be defaulted
                            pass
                await websocket.send(json.dumps(message))
