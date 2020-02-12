'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.defines import BUY, SELL, BID, ASK, TRADES, TICKER, L2_BOOK, VOLUME, POLONIEX
from cryptofeed.standards import pair_exchange_to_std, feed_to_exchange
from cryptofeed.pairs import poloniex_id_pair_mapping


LOG = logging.getLogger('feedhandler')


class Poloniex(Feed):
    id = POLONIEX

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        self.pair_mapping = poloniex_id_pair_mapping()
        super().__init__('wss://api2.poloniex.com',
                         pairs=pairs,
                         channels=channels,
                         callbacks=callbacks,
                         config=config,
                         **kwargs)
        """
        Due to the way poloniex subcriptions work, need to do some
        ugly manipulation of the config/channels,pairs to create a list
        of channels to subscribe to for poloniex as well as a callback map
        that we can use to determine if an update should be delivered to the
        end client or not
        """
        p_ticker = feed_to_exchange(self.id, TICKER)
        p_volume = feed_to_exchange(self.id, VOLUME)

        if channels:
            self.channels = self.pairs
            check = channels
            self.callback_map = {channel: set(pairs) for channel in channels if channel not in {p_ticker, p_volume}}
        elif config:
            self.channels = []
            for c, v in self.config.items():
                if c not in {p_ticker, p_volume}:
                    self.channels.extend(v)
            check = config
            self.callback_map = {key: set(value) for key, value in config.items()}

        if TICKER in check:
            self.channels.append(p_ticker)
        if VOLUME in check:
            self.channels.append(p_volume)
        # channels = pairs = cannot have duplicates
        self.channels = list(set(self.channels))

        self.__reset()

    def __do_callback(self, channel, pair):
        return channel in self.callback_map and pair in self.callback_map[channel]

    def __reset(self):
        self.l2_book = {}
        self.seq_no = {}

    async def _ticker(self, msg: dict, timestamp: float):
        # currencyPair, last, lowestAsk, highestBid, percentChange, baseVolume,
        # quoteVolume, isFrozen, 24hrHigh, 24hrLow
        pair_id, _, ask, bid, _, _, _, _, _, _ = msg
        pair = pair_exchange_to_std(self.pair_mapping[pair_id])
        if self.__do_callback(TICKER, pair):
            await self.callback(TICKER, feed=self.id,
                                        pair=pair,
                                        bid=Decimal(bid),
                                        ask=Decimal(ask),
                                        timestamp=timestamp)

    async def _volume(self, msg):
        # ['2018-01-02 00:45', 35361, {'BTC': '43811.201', 'ETH': '6747.243', 'XMR': '781.716', 'USDT': '196758644.806'}]
        # timestamp, exchange volume, dict of top volumes
        _, _, top_vols = msg
        for pair in top_vols:
            top_vols[pair] = Decimal(top_vols[pair])
        if self.__do_callback(VOLUME, pair):
            self.callbacks[VOLUME](feed=self.id, **top_vols)

    async def _book(self, msg: dict, chan_id: int, timestamp: float):
        delta = {BID: [], ASK: []}
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
                amount = Decimal(order_book[0][key])
                price = Decimal(key)
                self.l2_book[pair][ASK][price] = amount

            for key in order_book[1]:
                amount = Decimal(order_book[1][key])
                price = Decimal(key)
                self.l2_book[pair][BID][price] = amount
        else:
            pair = self.pair_mapping[chan_id]
            pair = pair_exchange_to_std(pair)
            for update in msg:
                msg_type = update[0]
                # order book update
                if msg_type == 'o':
                    side = ASK if update[1] == 0 else BID
                    price = Decimal(update[2])
                    amount = Decimal(update[3])
                    if amount == 0:
                        delta[side].append((price, 0))
                        del self.l2_book[pair][side][price]
                    else:
                        delta[side].append((price, amount))
                        self.l2_book[pair][side][price] = amount
                elif msg_type == 't':
                    # index 1 is trade id, 2 is side, 3 is price, 4 is amount, 5 is timestamp
                    _, order_id, _, price, amount, timestamp = update
                    price = Decimal(price)
                    amount = Decimal(amount)
                    side = BUY if update[2] == 1 else SELL
                    if self.__do_callback(TRADES, pair):
                        await self.callback(TRADES, feed=self.id,
                                                    pair=pair,
                                                    side=side,
                                                    amount=amount,
                                                    price=price,
                                                    timestamp=float(timestamp),
                                                    order_id=order_id)
                else:
                    LOG.warning("%s: Unexpected message received: %s", self.id, msg)

        if self.__do_callback(L2_BOOK, pair):
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp)

    async def message_handler(self, msg: str, timestamp: float):
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
                await self._ticker(msg[2], timestamp)
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

            if chan_id not in self.seq_no:
                self.seq_no[chan_id] = seq_no
            elif self.seq_no[chan_id] + 1 != seq_no and msg[2][0][0] != 'i':
                LOG.warning("%s: missing sequence number. Received %d, expected %d", self.id, seq_no, self.seq_no[chan_id] + 1)
                raise MissingSequenceNumber
            self.seq_no[chan_id] = seq_no
            if msg[2][0][0] == 'i':
                del self.seq_no[chan_id]
            await self._book(msg[2], chan_id, timestamp)
        elif chan_id == 1010:
            # heartbeat - ignore
            pass
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    async def subscribe(self, websocket):
        self.__reset()
        for channel in self.channels:
            await websocket.send(json.dumps({"command": "subscribe",
                                             "channel": channel
                                             }))
