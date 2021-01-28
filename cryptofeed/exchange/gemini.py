'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import List, Tuple, Callable

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.auth.gemini import generate_token
from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, GEMINI, L2_BOOK, SELL, TRADES, ORDER_INFO
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize, is_authenticated_channel


LOG = logging.getLogger('feedhandler')


class Gemini(Feed):
    id = GEMINI

    def __init__(self, sandbox=False, **kwargs):
        auth_api = 'wss://api.gemini.com' if not sandbox else 'wss://api.sandbox.gemini.com'
        super().__init__({'public': 'wss://api.gemini.com/v2/marketdata/', 'auth': f'{auth_api}/v1/order/events'}, **kwargs)

    def __reset(self, pairs):
        for pair in pairs:
            self.l2_book[symbol_exchange_to_std(pair)] = {BID: sd(), ASK: sd()}

    async def _book(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['symbol'])
        # Gemini sends ALL data for the symbol, so if we don't actually want
        # the book data, bail before parsing
        if self.channels and L2_BOOK not in self.channels:
            return
        if self.subscription and ((L2_BOOK in self.subscription and msg['symbol'] not in self.subscription[L2_BOOK]) or L2_BOOK not in self.subscription):
            return

        data = msg['changes']
        forced = not len(self.l2_book[pair][BID])
        delta = {BID: [], ASK: []}
        for entry in data:
            side = ASK if entry[0] == 'sell' else BID
            price = Decimal(entry[1])
            amount = Decimal(entry[2])
            if amount == 0:
                if price in self.l2_book[pair][side]:
                    del self.l2_book[pair][side][price]
                    delta[side].append((price, 0))
            else:
                self.l2_book[pair][side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['symbol'])
        price = Decimal(msg['price'])
        side = SELL if msg['side'] == 'sell' else BUY
        amount = Decimal(msg['quantity'])
        await self.callback(TRADES, feed=self.id,
                            order_id=msg['event_id'],
                            symbol=pair,
                            side=side,
                            amount=amount,
                            price=price,
                            timestamp=timestamp_normalize(self.id, msg['timestamp']),
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
                            symbol=symbol_exchange_to_std(msg['symbol'].upper()),  # This uses the REST endpoint format (lower case)
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

        for channel in self.subscription or self.channels:
            if is_authenticated_channel(channel):
                authenticated.extend(self.subscription.get(channel) or self.symbols)
            else:
                public.extend(self.subscription.get(channel) or self.symbols)

        if authenticated:
            header = generate_token(self.key_id, self.key_secret, "/v1/order/events", self.config.gemini.account_name)
            symbols = '&'.join([f"symbolFilter={s.lower()}" for s in authenticated])  # needs to match REST format (lower case)

            ret.append(self._connect_builder(f"{self.address['auth']}?{symbols}", None, header=header, sub=self._empty_subscribe, handler=self.message_handler_orders))
        if public:
            ret.append(self._connect_builder(self.address['public'], list(set(public))))

        return ret

    async def subscribe(self, conn: AsyncConnection, options=None):
        self.__reset(options)
        await conn.send(json.dumps({"type": "subscribe", "subscriptions": [{"name": "l2", "symbols": options}]}))
