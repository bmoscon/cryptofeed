'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, POLONIEX, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.poloniex_rest import PoloniexRestMixin
from cryptofeed.types import OrderBook, Trade, Ticker


LOG = logging.getLogger('feedhandler')


class Poloniex(Feed, PoloniexRestMixin):
    id = POLONIEX
    symbol_endpoint = 'https://poloniex.com/public?command=returnTicker'
    _channel_map = {}
    websocket_channels = {
        L2_BOOK: L2_BOOK,
        TRADES: TRADES,
        TICKER: 1002,
    }
    request_limit = 6

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}
        for symbol in data:
            cls._channel_map[data[symbol]['id']] = symbol
            std = symbol.replace("STR", "XLM")
            quote, base = std.split("_")
            s = Symbol(base, quote)
            ret[s.normalized] = symbol
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://api2.poloniex.com', **kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}
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
        t = Ticker(self.id, pair, Decimal(bid), Decimal(ask), None, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _book(self, msg: dict, chan_id: int, timestamp: float):
        delta = {BID: [], ASK: []}
        msg_type = msg[0][0]
        pair = None
        # initial update (i.e. snapshot)
        if msg_type == 'i':
            delta = None
            pair = msg[0][1]['currencyPair']
            pair = self.exchange_symbol_to_std_symbol(pair)
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
            # 0 is asks, 1 is bids
            order_book = msg[0][1]['orderBook']
            for index, side in enumerate([ASK, BID]):
                for key in order_book[index]:
                    amount = Decimal(order_book[index][key])
                    price = Decimal(key)
                    self._l2_book[pair].book[side][price] = amount
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
                        del self._l2_book[pair].book[side][price]
                    else:
                        delta[side].append((price, amount))
                        self._l2_book[pair].book[side][price] = amount
                elif msg_type == 't':
                    # index 1 is trade id, 2 is side, 3 is price, 4 is amount, 5 is timestamp, 6 is timestamp ms
                    _, order_id, _, price, amount, server_ts, _ = update
                    price = Decimal(price)
                    amount = Decimal(amount)
                    t = Trade(
                        self.id,
                        pair,
                        BUY if update[2] == 1 else SELL,
                        amount,
                        price,
                        float(server_ts),
                        id=order_id,
                        raw=msg
                    )
                    await self.callback(TRADES, t, timestamp)
                else:
                    LOG.warning("%s: Unexpected message received: %s", self.id, msg)

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, delta=delta, raw=msg)

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
