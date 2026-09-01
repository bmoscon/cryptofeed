'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple
import uuid

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BUY, L1_BOOK, L2_BOOK, SELL, TICKER, TRADES, UPBIT
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.connection import WebsocketEndpoint, RestEndpoint, Routes
from cryptofeed.types import L1Book, OrderBook, Ticker, Trade


LOG = logging.getLogger(__name__)


class Upbit(Feed):
    id = UPBIT
    book_delivery = 'snapshot'
    websocket_endpoints = [WebsocketEndpoint('wss://api.upbit.com/websocket/v1')]
    rest_endpoints = [RestEndpoint('https://api.upbit.com', routes=Routes('/v1/market/all'))]
    websocket_channels = {
        L2_BOOK: L2_BOOK,
        TRADES: TRADES,
        TICKER: TICKER,
        L1_BOOK: L1_BOOK,
    }
    request_limit = 10

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}
        for entry in data:
            quote, base = entry['market'].split("-")
            s = Symbol(base, quote)
            ret[s.normalized] = entry['market']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    async def _trade(self, msg: dict, timestamp: float):
        """
        Doc : https://docs.upbit.com/v1.0.7/reference#시세-체결-조회

        {
            'ty': 'trade'             // Event type
            'cd': 'KRW-BTC',          // Symbol
            'tp': 6759000.0,          // Trade Price
            'tv': 0.03243003,         // Trade volume(amount)
            'tms': 1584257228806,     // Timestamp
            'ttms': 1584257228000,    // Trade Timestamp
            'ab': 'BID',              // 'BID' or 'ASK'
            'cp': 64000.0,            // Change of price
            'pcp': 6823000.0,         // Previous closing price
            'sid': 1584257228000000,  // Sequential ID
            'st': 'SNAPSHOT',         // 'SNAPSHOT' or 'REALTIME'
            'td': '2020-03-15',       // Trade date utc
            'ttm': '07:27:08',        // Trade time utc
            'c': 'FALL',              // Change - 'FALL' / 'RISE' / 'EVEN'
        }
        """
        price = Decimal(msg['tp'])
        amount = Decimal(msg['tv'])
        t = Trade(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['cd']),
            BUY if msg['ab'] == 'BID' else SELL,
            amount,
            price,
            self.timestamp_normalize(msg['ttms']),
            id=str(msg['sid']),
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        """
        Doc : https://docs.upbit.com/v1.0.7/reference#시세-호가-정보orderbook-조회

        Currently, Upbit orderbook api only provides 15 depth book state and does not support delta

        {
            'ty': 'orderbook'       // Event type
            'cd': 'KRW-BTC',        // Symbol
            'obu': [{'ap': 6727000.0, 'as': 0.4744314, 'bp': 6721000.0, 'bs': 0.0014551},     // orderbook units
                    {'ap': 6728000.0, 'as': 1.85862302, 'bp': 6719000.0, 'bs': 0.00926683},
                    {'ap': 6729000.0, 'as': 5.43556558, 'bp': 6718000.0, 'bs': 0.40908977},
                    {'ap': 6730000.0, 'as': 4.41993651, 'bp': 6717000.0, 'bs': 0.48052204},
                    {'ap': 6731000.0, 'as': 0.09207, 'bp': 6716000.0, 'bs': 6.52612927},
                    {'ap': 6732000.0, 'as': 1.42736812, 'bp': 6715000.0, 'bs': 610.45535023},
                    {'ap': 6734000.0, 'as': 0.173, 'bp': 6714000.0, 'bs': 1.09218395},
                    {'ap': 6735000.0, 'as': 1.08739294, 'bp': 6713000.0, 'bs': 0.46785444},
                    {'ap': 6737000.0, 'as': 3.34450006, 'bp': 6712000.0, 'bs': 0.01300915},
                    {'ap': 6738000.0, 'as': 0.26, 'bp': 6711000.0, 'bs': 0.24701799},
                    {'ap': 6739000.0, 'as': 0.086, 'bp': 6710000.0, 'bs': 1.97964014},
                    {'ap': 6740000.0, 'as': 0.00658782, 'bp': 6708000.0, 'bs': 0.0002},
                    {'ap': 6741000.0, 'as': 0.8004, 'bp': 6707000.0, 'bs': 0.02022364},
                    {'ap': 6742000.0, 'as': 0.11040396, 'bp': 6706000.0, 'bs': 0.29082183},
                    {'ap': 6743000.0, 'as': 1.1, 'bp': 6705000.0, 'bs': 0.94493254}],
            'st': 'REALTIME',      // Streaming type - 'REALTIME' or 'SNAPSHOT'
            'tas': 20.67627941,    // Total ask size for given 15 depth (not total ask order size)
            'tbs': 622.93769692,   // Total bid size for given 15 depth (not total bid order size)
            'tms': 1584263923870,  // Timestamp
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['cd'])
        orderbook_timestamp = self.timestamp_normalize(msg['tms'])
        if pair not in self._l2_book:
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)

        self._l2_book[pair].book.bids = {Decimal(unit['bp']): Decimal(unit['bs']) for unit in msg['obu'] if unit['bp'] > 0}
        self._l2_book[pair].book.asks = {Decimal(unit['ap']): Decimal(unit['as']) for unit in msg['obu'] if unit['ap'] > 0}

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=orderbook_timestamp, raw=msg)

    @staticmethod
    def _top_of_book(msg: dict) -> Tuple[Dict, Dict]:
        """The best bid and ask units, or (None, None) when one side is empty.

        The units are ordered best first, but a level that has emptied is sent with a zero price and
        size rather than dropped, so the best level is the best *non-zero* one rather than obu[0].
        """
        bids = [unit for unit in msg['obu'] if unit['bp'] > 0 and unit['bs'] > 0]
        asks = [unit for unit in msg['obu'] if unit['ap'] > 0 and unit['as'] > 0]
        if not bids or not asks:
            return None, None
        return max(bids, key=lambda unit: unit['bp']), min(asks, key=lambda unit: unit['ap'])

    async def _ticker(self, msg: dict, timestamp: float):
        """The venue's own ticker stream is 24h statistics and carries no bid or ask, so - as on
        Bithumb, whose API this one is the template for - the bid/ask pair comes from the top of the
        orderbook stream."""
        bid, ask = self._top_of_book(msg)
        if bid is None:
            return

        t = Ticker(self.id, self.exchange_symbol_to_std_symbol(msg['cd']), Decimal(bid['bp']), Decimal(ask['ap']), self.timestamp_normalize(msg['tms']), raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _l1_book(self, msg: dict, timestamp: float):
        """Top of book with sizes, which the Ticker has no room for."""
        bid, ask = self._top_of_book(msg)
        if bid is None:
            return

        book = L1Book(self.id,
                      self.exchange_symbol_to_std_symbol(msg['cd']),
                      Decimal(bid['bp']),
                      Decimal(bid['bs']),
                      Decimal(ask['ap']),
                      Decimal(ask['as']),
                      self.timestamp_normalize(msg['tms']),
                      raw=msg)
        await self.callback(L1_BOOK, book, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if msg['ty'] == "trade":
            await self._trade(msg, timestamp)
        elif msg['ty'] == "orderbook":
            # three channels ride this stream
            if L2_BOOK in conn.subscription:
                await self._book(msg, timestamp)
            if TICKER in conn.subscription:
                await self._ticker(msg, timestamp)
            if L1_BOOK in conn.subscription:
                await self._l1_book(msg, timestamp)
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        """
        Doc : https://docs.upbit.com/docs/upbit-quotation-websocket

        For subscription, ticket information is commonly required.
        In order to reduce the data size, format parameter is set to 'SIMPLE' instead of 'DEFAULT'


        Examples (Note that the positions of the base and quote currencies are swapped.)

        1. In order to get TRADES of "BTC-KRW" and "XRP-BTC" markets.
        > [{"ticket":"UNIQUE_TICKET"},{"type":"trade","codes":["KRW-BTC","BTC-XRP"]}]

        2. In order to get ORDERBOOK of "BTC-KRW" and "XRP-BTC" markets.
        > [{"ticket":"UNIQUE_TICKET"},{"type":"orderbook","codes":["KRW-BTC","BTC-XRP"]}]

        3. In order to get TRADES of "BTC-KRW" and ORDERBOOK of "ETH-KRW"
        > [{"ticket":"UNIQUE_TICKET"},{"type":"trade","codes":["KRW-BTC"]},{"type":"orderbook","codes":["KRW-ETH"]}]

        4. In order to get TRADES of "BTC-KRW", ORDERBOOK of "ETH-KRW and TICKER of "EOS-KRW"
        > [{"ticket":"UNIQUE_TICKET"},{"type":"trade","codes":["KRW-BTC"]},{"type":"orderbook","codes":["KRW-ETH"]},{"type":"ticker", "codes":["KRW-EOS"]}]

        5. In order to get TRADES of "BTC-KRW", ORDERBOOK of "ETH-KRW and TICKER of "EOS-KRW" with in shorter format
        > [{"ticket":"UNIQUE_TICKET"},{"format":"SIMPLE"},{"type":"trade","codes":["KRW-BTC"]},{"type":"orderbook","codes":["KRW-ETH"]},{"type":"ticker", "codes":["KRW-EOS"]}]
        """

        chans = [{"ticket": uuid.uuid4()}, {"format": "SIMPLE"}]
        # ticker and top of book are served off the orderbook stream, so all three collapse onto one
        # subscription rather than asking the venue for a stream it does not have
        book = []
        for chan in (L2_BOOK, TICKER, L1_BOOK):
            for code in self.subscription.get(chan, []):
                if code not in book:
                    book.append(code)
        if book:
            chans.append({"type": "orderbook", "codes": book, 'isOnlyRealtime': True})
        if self.subscription.get(TRADES):
            chans.append({"type": "trade", "codes": list(self.subscription[TRADES]), 'isOnlyRealtime': True})

        await conn.write(json.dumps(chans))
