'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, List, Tuple, Callable

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.auth.gemini import generate_token
from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, GEMINI, L2_BOOK, SELL, TRADES, ORDER_INFO
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.gemini_rest import GeminiRestMixin


LOG = logging.getLogger('feedhandler')


class Gemini(Feed, GeminiRestMixin):
    id = GEMINI
    symbol_endpoint = {'https://api.gemini.com/v1/symbols': 'https://api.gemini.com/v1/symbols/details/'}
    websocket_channels = {
        L2_BOOK: L2_BOOK,
        TRADES: TRADES,
        ORDER_INFO: ORDER_INFO
    }
    request_limit = 1

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for symbol in data:
            if symbol['status'] == 'closed':
                continue
            s = Symbol(symbol['base_currency'], symbol['quote_currency'])
            ret[s.normalized] = symbol['symbol']
            info['tick_size'][s.normalized] = symbol['tick_size']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, sandbox=False, **kwargs):
        auth_api = 'wss://api.gemini.com' if not sandbox else 'wss://api.sandbox.gemini.com'
        super().__init__({'public': 'wss://api.gemini.com/v2/marketdata/', 'auth': f'{auth_api}/v1/order/events'}, **kwargs)

    def __reset(self, pairs):
        for pair in pairs:
            self._l2_book[self.exchange_symbol_to_std_symbol(pair)] = {BID: sd(), ASK: sd()}

    async def _book(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        # Gemini sends ALL data for the symbol, so if we don't actually want
        # the book data, bail before parsing
        if self.subscription and ((L2_BOOK in self.subscription and msg['symbol'] not in self.subscription[L2_BOOK]) or L2_BOOK not in self.subscription):
            return

        data = msg['changes']
        forced = not len(self._l2_book[pair][BID])
        delta = {BID: [], ASK: []}
        for entry in data:
            side = ASK if entry[0] == 'sell' else BID
            price = Decimal(entry[1])
            amount = Decimal(entry[2])
            if amount == 0:
                if price in self._l2_book[pair][side]:
                    del self._l2_book[pair][side][price]
                    delta[side].append((price, 0))
            else:
                self._l2_book[pair][side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(self._l2_book[pair], L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        price = Decimal(msg['price'])
        side = SELL if msg['side'] == 'sell' else BUY
        amount = Decimal(msg['quantity'])
        await self.callback(TRADES, feed=self.id,
                            order_id=msg['event_id'],
                            symbol=pair,
                            side=side,
                            amount=amount,
                            price=price,
                            timestamp=self.timestamp_normalize(msg['timestamp']),
                            receipt_timestamp=timestamp)

    async def _order(self, msg: dict, timestamp: float):
        if msg['type'] == "initial" or msg['type'] == "booked":
            status = "active"
        elif msg['type'] == "fill":
            status = 'filled'
        else:
            status = msg['type']

        keys = ('executed_amount', 'remaining_amount', 'original_amount', 'price', 'avg_execution_price', 'total_spend')
        data = {k: Decimal(msg[k]) for k in keys if k in msg}

        await self.callback(ORDER_INFO, feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['symbol'].upper()),  # This uses the REST endpoint format (lower case)
                            status=status,
                            order_id=msg['order_id'],
                            side=BUY if msg['side'].lower() == 'buy' else SELL,
                            order_type=msg['order_type'],
                            timestamp=msg['timestampms'] / 1000.0,
                            receipt_timestamp=timestamp,
                            **data
                            )

    async def message_handler_orders(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg, list):
            for entry in msg:
                await self._order(entry, timestamp)
        elif isinstance(msg, dict):
            if msg['type'] == 'subscription_ack':
                LOG.info('%s: Authenticated successfully', self.id)
            elif msg['type'] == 'heartbeat':
                return
            else:
                await self._order(msg, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['type'] == 'l2_updates':
            await self._book(msg, timestamp)
        elif msg['type'] == 'trade':
            await self._trade(msg, timestamp)
        elif msg['type'] == 'heartbeat':
            return
        elif msg['type'] == 'auction_result' or msg['type'] == 'auction_indicative' or msg['type'] == 'auction_open':
            return
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        authenticated = []
        public = []
        ret = []

        for channel in self.subscription:
            if self.is_authenticated_channel(channel):
                authenticated.extend(self.subscription.get(channel))
            else:
                public.extend(self.subscription.get(channel))

        if authenticated:
            header = generate_token(self.key_id, self.key_secret, "/v1/order/events", self.config.gemini.account_name)
            symbols = '&'.join([f"symbolFilter={s.lower()}" for s in authenticated])  # needs to match REST format (lower case)

            ret.append(self._connect_builder(f"{self.address['auth']}?{symbols}", None, header=header, sub=self._empty_subscribe, handler=self.message_handler_orders))
        if public:
            ret.append(self._connect_builder(self.address['public'], list(set(public))))

        return ret

    async def subscribe(self, conn: AsyncConnection, options=None):
        self.__reset(options)
        await conn.write(json.dumps({"type": "subscribe", "subscriptions": [{"name": "l2", "symbols": options}]}))
