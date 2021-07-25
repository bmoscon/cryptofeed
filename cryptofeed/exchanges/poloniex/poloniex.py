'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, POLONIEX, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed


LOG = logging.getLogger('feedhandler')


class Poloniex(Feed):
    id = POLONIEX
    symbol_endpoint = 'https://poloniex.com/public?command=returnTicker'
    _channel_map = {}

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        for symbol in data:
            cls._channel_map[data[symbol]['id']] = symbol
            std = symbol.replace("STR", "XLM")
            quote, base = std.split("_")
            std = f"{base}{symbol_separator}{quote}"
            ret[std] = symbol
        return ret, {}

    def __init__(self, **kwargs):
        super().__init__('wss://api2.poloniex.com', **kwargs)
        self.__reset()

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
        if pair_id not in self._channel_map:
            # Ignore new trading pairs that are added during long running sessions
            return
        pair = self.exchange_symbol_to_std_symbol(self._channel_map[pair_id])
        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=Decimal(bid),
                            ask=Decimal(ask),
                            timestamp=timestamp,
                            receipt_timestamp=timestamp)

    async def _book(self, msg: dict, chan_id: int, timestamp: float):
        delta = {BID: [], ASK: []}
        msg_type = msg[0][0]
        pair = None
        forced = False
        # initial update (i.e. snapshot)
        if msg_type == 'i':
            forced = True
            pair = msg[0][1]['currencyPair']
            pair = self.exchange_symbol_to_std_symbol(pair)
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
            pair = self._channel_map[chan_id]
            pair = self.exchange_symbol_to_std_symbol(pair)
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
                    # index 1 is trade id, 2 is side, 3 is price, 4 is amount, 5 is timestamp, 6 is timestamp ms
                    _, order_id, _, price, amount, server_ts, _ = update
                    price = Decimal(price)
                    amount = Decimal(amount)
                    side = BUY if update[2] == 1 else SELL
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
            if seq_id is None and self._channel_map[msg[2][0]] in self.subscription[1002]:
                await self._ticker(msg[2], timestamp)
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
            symbol = self._channel_map[chan_id]
            if symbol in self._trade_book_symbols:
                await self._book(msg[2], chan_id, timestamp)
        elif chan_id == 1010:
            # heartbeat - ignore
            pass
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        self._trade_book_symbols = []
        for chan in self.subscription:
            if chan == L2_BOOK or chan == TRADES:
                for symbol in self.subscription[chan]:
                    if symbol in self._trade_book_symbols:
                        continue
                    self._trade_book_symbols.append(symbol)
                    await conn.write(json.dumps({"command": "subscribe", "channel": symbol}))
            else:
                await conn.write(json.dumps({"command": "subscribe", "channel": chan}))
        self._trade_book_symbols = set(self._trade_book_symbols)
