'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
from collections import defaultdict
import time

from sortedcontainers import SortedDict as sd

from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.defines import BID, ASK, TRADES, TICKER, L2_BOOK, VOLUME, UPD, DEL
from cryptofeed.standards import pair_exchange_to_std
from cryptofeed.exchanges import POLONIEX
from .pairs import poloniex_id_pair_mapping


LOG = logging.getLogger('feedhandler')


class Poloniex(Feed):
    id = POLONIEX

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        if pairs:
            LOG.error("Poloniex does not support pairs")
            raise ValueError("Poloniex does not support pairs")

        super().__init__('wss://api2.poloniex.com',
                         channels=channels,
                         callbacks=callbacks,
                         **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}
        self.seq_no = {}

    async def _ticker(self, msg):
        # currencyPair, last, lowestAsk, highestBid, percentChange, baseVolume,
        # quoteVolume, isFrozen, 24hrHigh, 24hrLow
        pair_id, _, ask, bid, _, _, _, _, _, _ = msg
        pair = pair_exchange_to_std(poloniex_id_pair_mapping[pair_id])
        await self.callbacks[TICKER](feed=self.id,
                                     pair=pair,
                                     bid=bid,
                                     ask=ask)

    async def _volume(self, msg):
        # ['2018-01-02 00:45', 35361, {'BTC': '43811.201', 'ETH': '6747.243', 'XMR': '781.716', 'USDT': '196758644.806'}]
        # timestamp, exchange volume, dict of top volumes
        _, _, top_vols = msg
        for pair in top_vols:
            top_vols[pair] = top_vols[pair]
        self.callbacks[VOLUME](feed=self.id, **top_vols)

    async def _book(self, msg, chan_id):
        timestamp = time.time()
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
        msg_type = msg[0][0]
        pair = None
        forced = False
        # initial update (i.e. snapshot)
        if msg_type == 'i':
            forced = True
            pair = msg[0][1]['currencyPair']
            pair = pair_exchange_to_std(pair)
            self.l2_book[pair] = {BID: sd(), ASK: sd()}
            # 0 is asks, 1 is bids
            order_book = msg[0][1]['orderBook']
            for key in order_book[0]:
                amount = order_book[0][key]
                price = key
                self.l2_book[pair][ASK][price] = amount

            for key in order_book[1]:
                amount = order_book[1][key]
                price = key
                self.l2_book[pair][BID][price] = amount
        else:
            pair = poloniex_id_pair_mapping[chan_id]
            pair = pair_exchange_to_std(pair)
            for update in msg:
                msg_type = update[0]
                # order book update
                if msg_type == 'o':
                    side = ASK if update[1] == 0 else BID
                    price = update[2]
                    amount = update[3]
                    if amount == 0:
                        delta[side][DEL].append(price)
                        del self.l2_book[pair][side][price]
                    else:
                        delta[side][UPD].append((price, amount))
                        self.l2_book[pair][side][price] = amount
                elif msg_type == 't':
                    # index 1 is trade id, 2 is side, 3 is price, 4 is amount, 5 is timestamp
                    _, order_id, _, price, amount, timestamp = update
                    side = ASK if update[2] == 0 else BID
                    await self.callbacks[TRADES](feed=self.id,
                                                 pair=pair,
                                                 side=side,
                                                 amount=amount,
                                                 price=price,
                                                 timestamp=timestamp,
                                                 order_id=order_id)
                else:
                    LOG.warning("%s: Unexpected message received: %s", self.id, msg)

        await self.book_callback(pair, L2_BOOK, forced, delta, timestamp)

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'error' in msg:
            LOG.error("%s: Error from exchange: %s", self.id, msg)
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
        elif chan_id < 1000:
            # order book updates - the channel id refers to
            # the trading pair being updated
            seq_no = msg[1]

            if chan_id not in self.seq_no :
                self.seq_no[chan_id] = seq_no
            elif self.seq_no[chan_id] + 1 != seq_no:
                LOG.warning("%s: missing sequence number. Received %d, expected %d", self.id, seq_no, self.seq_no+1)
                self.__reset()
                raise MissingSequenceNumber
            self.seq_no[chan_id] = seq_no
            await self._book(msg[2], chan_id)
        elif chan_id == 1010:
            # heartbeat - ignore
            pass
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    async def subscribe(self, websocket):
        for channel in self.channels:
            await websocket.send(json.dumps({"command": "subscribe",
                                             "channel": channel
                                            }))
