'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std


class Bitfinex(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(Bitfinex, self).__init__('wss://api.bitfinex.com/ws/2')
        self.pairs = [pair_std_to_exchange(pair, 'BITFINEX') for pair in pairs]
        self.channels = channels
        '''
        maps channel id (int) to a dict of
           symbol: channel's currency
           channel: channel name
           handler: the handler for this channel type
        '''
        self.channel_map = {}
        self.book = {}
        self.order_map = {}
        self.callbacks = {'trades': Callback(None), 'ticker': Callback(None), 'book': Callback(None)}

        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    async def _ticker(self, msg):
        chan_id = msg[0]
        if msg[1] == 'hb':
            # ignore heartbeats
            pass
        else:
            # bid, bid_ask, ask, ask_size, daily_change, daily_change_percent,
            # last_price, volume, high, low
            bid, _, ask, _, _, _, _, _, _, _ = msg[1]
            pair = self.channel_map[chan_id]['symbol']
            pair = pair_exchange_to_std(pair)
            await self.callbacks['ticker'](feed='bitfinex',
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
                side = 'SELL'
            else:
                side = 'BUY'
            amount = abs(amount)
            await self.callbacks['trades'](feed='bitfinex',
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
                print("Unexpected trade message {}".format(msg))

    async def _book(self, msg):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)

        if isinstance(msg[1], list):
            if isinstance(msg[1][0], list):
                # snapshot so clear book
                self.book[pair] = {'bid': sd(), 'ask': sd()}
                for update in msg[1]:
                    price, count, amount = [Decimal(x) for x in update]
                    if amount > 0:
                        side = 'bid'
                    else:
                        side = 'ask'
                        amount = abs(amount)
                    self.book[pair][side][price] = {'count': count, 'amount': amount}
            else:
                # book update
                price, count, amount = [Decimal(x) for x in msg[1]]

                if amount > 0:
                    side = 'bid'
                else:
                    side = 'ask'
                    amount = abs(amount)

                if count > 0:
                    # change at price level
                    self.book[pair][side][price] = {'count': count, 'amount': amount}
                else:
                    # remove price level
                    del self.book[pair][side][price]
        elif msg[1] == 'hb':
            pass
        else:
            print("Unexpected book msg {}".format(msg))
        await self.callbacks['book'](feed='bitfinex', book=self.book)

    async def _raw_book(self, msg):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)

        if isinstance(msg[1], list):
            if isinstance(msg[1][0], list):
                # snapshot so clear book
                self.book[pair] = {'bid': sd(), 'ask': sd()}
                for update in msg[1]:
                    order_id, price, amount = update
                    price = Decimal(price)
                    amount = Decimal(amount)

                    if amount > 0:
                        side = 'bid'
                    else:
                        side = 'ask'
                        amount = abs(amount)

                    if price not in self.book[pair][side]:
                        self.book[pair][side][price] = {'count': 1, 'amount': amount}
                        self.order_map[order_id] = {'price': price, 'amount': amount, 'side': side}
                    else:
                        self.book[pair][side][price]['count'] += 1
                        self.book[pair][side][price]['amount'] += amount
                        self.order_map[order_id] = {'price': price, 'amount': amount, 'side': side}
            else:
                # book update
                order_id, price, amount = [Decimal(x) for x in msg[1]]

                if amount > 0:
                    side = 'bid'
                else:
                    side = 'ask'
                    amount = abs(amount)

                if price == 0:
                    price = self.order_map[order_id]['price']
                    self.book[pair][side][price]['count'] -= 1
                    if self.book[pair][side][price]['count'] == 0:
                        del self.book[pair][side][price]
                    del self.order_map[order_id]
                else:
                    self.order_map[order_id] = {'price': price, 'amount': amount, 'side': side}
                    if price in self.book[pair][side]:
                        self.book[pair][side][price]['count'] += 1
                        self.book[pair][side][price]['amount'] += amount
                    else:
                        self.book[pair][side][price] = {'count': 1, 'amount': amount}
        elif msg[1] == 'hb':
            pass
        else:
            print("Unexpected book msg {}".format(msg))
        await self.callbacks['book'](feed='bitfinex', book=self.book)

    async def message_handler(self, msg):
        msg = json.loads(msg)
        if isinstance(msg, list):
            chan_id = msg[0]
            if chan_id in self.channel_map:
                await self.channel_map[chan_id]['handler'](msg)
            else:
                print("Unexpected message on unregistered channel {}".format(msg))
        elif 'event' in msg and msg['event'] == 'error':
            print("Error: {}".format(msg['msg']))
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
                print('Invalid message type {}'.format(msg))
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
