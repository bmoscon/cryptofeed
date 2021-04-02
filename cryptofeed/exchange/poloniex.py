'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import calendar
import logging
import time
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, POLONIEX, SELL, TICKER, TRADES, VOLUME
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import poloniex_id_symbol_mapping
from cryptofeed.standards import feed_to_exchange, symbol_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Poloniex(Feed):
    id = POLONIEX

    def __init__(self, symbols=None, channels=None, subscription=None, **kwargs):
        self.pair_mapping = poloniex_id_symbol_mapping()
        super().__init__('wss://api2.poloniex.com',
                         symbols=symbols,
                         channels=channels,
                         subscription=subscription,
                         **kwargs)
        """
        Due to the way Poloniex subscriptions work, need to do some
        ugly manipulation of the subscription/channels,pairs to create a list
        of channels to subscribe to for Poloniex as well as a callback map
        that we can use to determine if an update should be delivered to the
        end client or not
        """
        p_ticker = feed_to_exchange(self.id, TICKER)
        p_volume = feed_to_exchange(self.id, VOLUME)

        if channels:
            self.channels = self.symbols
            check = channels
            self.callback_map = {chan: set(symbols) for chan in channels if chan not in {p_ticker, p_volume}}
        elif subscription:
            self.channels = []
            for c, v in self.subscription.items():
                if c not in {p_ticker, p_volume}:
                    self.channels.extend(v)
            check = subscription
            self.callback_map = {key: set(value) for key, value in subscription.items()}
        else:
            raise ValueError(f'{self.id}: the arguments channels and subscription are empty - cannot subscribe')

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
        """
        Format:

        currencyPair, last, lowestAsk, highestBid, percentChange, baseVolume,
        quoteVolume, isFrozen, 24hrHigh, 24hrLow, postOnly, maintenance mode

        The postOnly field indicates that new orders posted to the market must be non-matching orders (no taker orders).
        Any orders that would match will be rejected. Maintenance mode indicates that maintenace is being performed
        and orders will be rejected
        """
        pair_id, _, ask, bid, _, _, _, _, _, _, _, _ = msg
        if pair_id not in self.pair_mapping:
            # Ignore new trading pairs that are added during long running sessions
            return
        pair = symbol_exchange_to_std(self.pair_mapping[pair_id])
        if self.__do_callback(TICKER, pair):
            await self.callback(TICKER, feed=self.id,
                                symbol=pair,
                                bid=Decimal(bid),
                                ask=Decimal(ask),
                                timestamp=timestamp,
                                receipt_timestamp=timestamp)

    async def _volume(self, msg: list, timestamp: float):
        # ['2018-01-02 00:45', 35361, {'BTC': '43811.201', 'ETH': '6747.243', 'XMR': '781.716', 'USDT': '196758644.806'}]
        # timestamp, exchange volume, dict of top volumes
        server_timestamp, exchange_vol, top_vols = msg
        server_timestamp = calendar.timegm(time.strptime(server_timestamp, '%Y-%m-%d %H:%M'))
        for pair in top_vols:
            top_vols[pair] = Decimal(top_vols[pair])

        await self.callback(VOLUME, feed=self.id, exchange_volume=exchange_vol, timestamp=server_timestamp, receipt_timestamp=timestamp, **top_vols)

    async def _book(self, msg: dict, chan_id: int, timestamp: float):
        delta = {BID: [], ASK: []}
        msg_type = msg[0][0]
        pair = None
        forced = False
        # initial update (i.e. snapshot)
        if msg_type == 'i':
            forced = True
            pair = msg[0][1]['currencyPair']
            pair = symbol_exchange_to_std(pair)
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
            pair = symbol_exchange_to_std(pair)
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
                    _, order_id, _, price, amount, server_ts = update
                    price = Decimal(price)
                    amount = Decimal(amount)
                    side = BUY if update[2] == 1 else SELL
                    if self.__do_callback(TRADES, pair):
                        await self.callback(TRADES, feed=self.id,
                                            symbol=pair,
                                            side=side,
                                            amount=amount,
                                            price=price,
                                            timestamp=float(server_ts),
                                            order_id=order_id,
                                            receipt_timestamp=timestamp)
                else:
                    LOG.warning("%s: Unexpected message received: %s", self.id, msg)

        if self.__do_callback(L2_BOOK, pair):
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

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
                await self._volume(msg[2], timestamp)
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

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.channels:
            await conn.send(json.dumps({"command": "subscribe", "channel": chan}))
