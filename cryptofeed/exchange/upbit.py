import logging
from decimal import Decimal
import uuid

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, SELL, TICKER, TRADES, UPBIT
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Upbit(Feed):
    id = UPBIT
    api = 'https://api.upbit.com/v1/'

    def __init__(self, **kwargs):
        super().__init__('wss://api.upbit.com/websocket/v1', **kwargs)

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
        await self.callback(TRADES, feed=self.id,
                            order_id=msg['sid'],
                            symbol=symbol_exchange_to_std(msg['cd']),
                            side=BUY if msg['ab'] == 'BID' else SELL,
                            amount=amount,
                            price=price,
                            timestamp=timestamp_normalize(self.id, msg['ttms']),
                            receipt_timestamp=timestamp)

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
        pair = symbol_exchange_to_std(msg['cd'])
        orderbook_timestamp = timestamp_normalize(self.id, msg['tms'])
        forced = pair not in self.l2_book

        update = {
            BID: sd({
                Decimal(unit['bp']): Decimal(unit['bs'])
                for unit in msg['obu'] if unit['bp'] > 0
            }),
            ASK: sd({
                Decimal(unit['ap']): Decimal(unit['as'])
                for unit in msg['obu'] if unit['ap'] > 0
            })
        }

        if not forced:
            self.previous_book[pair] = self.l2_book[pair]
        self.l2_book[pair] = update

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, False, orderbook_timestamp, timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        Doc : https://docs.upbit.com/v1.0.7/reference#시세-ticker-조회

        {
            'ty': 'ticker'                // Event type
            'cd': 'KRW-BTC',              // Symbol
            'hp': 6904000.0,              // High price
            'lp': 6660000.0,              // Low price
            'cp': 81000.0,                // Change price
            'tp': 6742000.0,              // Trade price
            'tv': 0.022112,               // Trade volume(amount)
            'op': 6823000.0,              // Opening price
            'pcp': 6823000.0,             // Previous closing price
            'st': 'REALTIME',             // 'SNAPSHOT' or 'REALTIME'
            'tms': 1584261867032,         // Receipt timestamp
            'ttms': 1584261866000,        // Trade timestamp
            'ab': 'ASK',                  // 'BID' or 'ASK'
            'aav': 1223.62809015,
            'abv': 1273.40780697,
            'atp': 16904032846.03822,
            'atp24h': 60900534403.85303,
            'atv': 2497.03589712,
            'atv24h': 8916.84161476,
            'c': 'FALL',                 // Change - 'FALL' / 'RISE' / 'EVEN'
            'cr': 0.0118716107,
            'dd': None,
            'h52wdt': '2019-06-26',
            'h52wp': 16840000.0,
            'its': False,
            'l52wdt': '2019-03-17',
            'l52wp': 4384000.0,
            'ms': 'ACTIVE',              // Market Status 'ACTIVE' or
            'msfi': None,
            'mw': 'NONE',                // Market warning 'NONE' or
            'scp': -81000.0,
            'scr': -0.0118716107,
            'tdt': '20200315',
            'ts': None,
            'ttm': '084426',
        }

        """

        # Currently, Upbit ticker api does not support best_ask and best_bid price.
        # Only way for tracking best_ask and best_bid price is looking at the orderbook directly.
        raise NotImplementedError

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if msg['ty'] == "trade":
            await self._trade(msg, timestamp)
        elif msg['ty'] == "orderbook":
            await self._book(msg, timestamp)
        elif msg['ty'] == "ticker":
            await self._ticker(msg, timestamp)
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
        for chan in set(self.channels or self.subscription):
            codes = list(set(self.symbols or self.subscription[chan]))
            if chan == L2_BOOK:
                chans.append({"type": "orderbook", "codes": codes, 'isOnlyRealtime': True})
            if chan == TRADES:
                chans.append({"type": "trade", "codes": codes, 'isOnlyRealtime': True})
            if chan == TICKER:
                chans.append({"type": "ticker", "codes": codes, 'isOnlyRealtime': True})

        await conn.send(json.dumps(chans))
