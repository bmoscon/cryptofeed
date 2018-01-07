'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
from decimal import Decimal

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std
from .pairs import poloniex_id_pair_mapping


class Poloniex(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(Poloniex, self).__init__('wss://api2.poloniex.com')
        self.channels = channels
        self.book = {}
        if pairs:
            raise ValueError("Poloniex does not support pairs on a channel")

        self.callbacks = {'trades': Callback(None),
                          'ticker': Callback(None),
                          'book': Callback(None),
                          'volume': Callback(None)}

        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    async def _ticker(self, msg):
        # currencyPair, last, lowestAsk, highestBid, percentChange, baseVolume,
        # quoteVolume, isFrozen, 24hrHigh, 24hrLow
        pair_id, _, ask, bid, _, _, _, _, _, _ = msg
        pair = poloniex_id_pair_mapping[pair_id]
        await self.callbacks['ticker'](feed='poloniex',
                                       pair=pair,
                                       bid=Decimal(bid),
                                       ask=Decimal(ask))

    async def _volume(self, msg):
        # ['2018-01-02 00:45', 35361, {'BTC': '43811.201', 'ETH': '6747.243', 'XMR': '781.716', 'USDT': '196758644.806'}]
        # timestamp, exchange volume, dict of top volumes
        _, _, top_vols = msg
        for pair in top_vols:
            top_vols[pair] = Decimal(top_vols[pair])
        self.callbacks['volume'](feed='poloniex', **top_vols)

    async def _book(self, msg, chan_id):
        msg_type = msg[0][0]
        # initial update (i.e. snapshot)
        if msg_type == 'i':
            pair = msg[0][1]['currencyPair']
            pair = pair_exchange_to_std(pair)
            self.book[pair] = {'bid': {}, 'ask': {}}
            # 0 is asks, 1 is bids
            order_book = msg[0][1]['orderBook']
            for key in order_book[0]:
                amount = Decimal(order_book[0][key])
                price = Decimal(key)
                self.book[pair]['ask'][price] = amount

            for key in order_book[1]:
                amount = Decimal(order_book[1][key])
                price = Decimal(key)
                self.book[pair]['bid'][price] = amount
        else:
            pair = poloniex_id_pair_mapping[chan_id]
            pair = pair_exchange_to_std(pair)
            for update in msg:
                msg_type = update[0]
                # order book update
                if msg_type == 'o':
                    side = 'ask' if update[1] == 0 else 'bid'
                    price = Decimal(update[2])
                    amount = Decimal(update[3])
                    if amount == 0:
                        del self.book[pair][side][price]
                    else:
                        self.book[pair][side][price] = amount
                elif msg_type == 't':
                    # index 1 is trade id, 2 is side, 3 is price, 4 is amount, 5 is timestamp
                    price = Decimal(update[3])
                    side = 'ask' if update[2] == 0 else 'bid'
                    amount = Decimal(update[4])
                    await self.callbacks['trades'](feed='poloniex',
                                                   pair=pair,
                                                   side=side,
                                                   amount=amount,
                                                   price=price)
                else:
                    print("Unexpected message received: {}".format(msg))
        await self.callbacks['book'](feed='poloniex', book=self.book)

    async def message_handler(self, msg):
        msg = json.loads(msg)
        if 'error' in msg:
            print("Error from exchange: {}".format(msg))
            return

        chan_id = msg[0]
        if chan_id == 1002:
            # the ticker channel doesn't have sequence ids
            # so it should be None, except for the subscription
            # ack, in which case its 1
            seq_id = msg[1]
            if seq_id is None:
                await self._ticker(msg[2])
        elif chan_id == 1003:
            # volume update channel is just like ticker - the
            # sequence id is None except for the initial ack
            seq_id = msg[1]
            if seq_id is None:
                await self._volume(msg[2])
        elif chan_id <= 200:
            # order book updates - the channel id refers to
            # the trading pair being updated
            await self._book(msg[2], chan_id)
        elif chan_id == 1010:
            # heartbeat - ignore
            pass
        else:
            print('Invalid message type {}'.format(msg))

    async def subscribe(self, websocket):
        for channel in self.channels:
            chan = pair_std_to_exchange(channel, 'POLONIEX')
            if chan:
                channel = chan
            await websocket.send(json.dumps({"command": "subscribe",
                                             "channel": channel
                                            }))
