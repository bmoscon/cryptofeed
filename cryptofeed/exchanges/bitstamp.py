'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BITSTAMP, BUY, L2_BOOK, L3_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade


LOG = logging.getLogger(__name__)


class Bitstamp(Feed):
    id = BITSTAMP
    CROSSED_BOOKS_ARE_DOCUMENTED=True
    # API documentation: https://www.bitstamp.net/websocket/v2/
    # Crossed books are possible and expected, see https://www.bitstamp.net/websocket/v2/ under 'Note on crossed order book'
    websocket_endpoints = [WebsocketEndpoint('wss://ws.bitstamp.net/', options={'compression': None})]
    rest_endpoints = [RestEndpoint('https://www.bitstamp.net', routes=Routes('/api/v2/trading-pairs-info/', l2book='/api/v2/order_book/{}'))]
    websocket_channels = {
        L3_BOOK: 'detail_order_book',
        L2_BOOK: 'order_book',
        TRADES: 'live_trades',
    }
    request_limit = 13
    book_delivery = 'snapshot'

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1_000_000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}

        for d in data:
            if d['trading'] != 'Enabled':
                continue
            base, quote = d['name'].split("/")
            s = Symbol(base, quote)
            symbol = d['url_symbol']
            ret[s.normalized] = symbol
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}

    async def _process_l2_book(self, msg: dict, timestamp: float):
        data = msg['data']
        pair = self.exchange_symbol_to_std_symbol(msg['channel'].split('_')[-1])

        book = OrderBook(self.id, pair, max_depth=self.max_depth,
                         bids={Decimal(price): Decimal(size) for price, size, *_ in data['bids']},
                         asks={Decimal(price): Decimal(size) for price, size, *_ in data['asks']})
        self._l2_book[pair] = book
        await self.book_callback(L2_BOOK, book, timestamp, raw=msg, timestamp=self.timestamp_normalize(int(data['microtimestamp'])))

    async def _process_l3_book(self, msg: dict, timestamp: float):
        data = msg['data']
        chan = msg['channel']
        ts = int(data['microtimestamp'])
        pair = self.exchange_symbol_to_std_symbol(chan.split('_')[-1])

        book = OrderBook(self.id, pair, max_depth=self.max_depth)
        for side in (BID, ASK):
            for price, size, order_id in data[side + 's']:
                price = Decimal(price)
                size = Decimal(size)
                if price in book.book[side]:
                    book.book[side][price][order_id] = size
                else:
                    book.book[side][price] = {order_id: size}

        self._l3_book[pair] = book
        await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, timestamp=self.timestamp_normalize(ts), raw=msg)

    async def _trades(self, msg: dict, timestamp: float):
        """
        {'data':
         {
         'microtimestamp': '1562650233964229',      // Event time (micros)
         'amount': Decimal('0.014140160000000001'), // Quantity
         'buy_order_id': 3709484695,                // Buyer order ID
         'sell_order_id': 3709484799,               // Seller order ID
         'amount_str': '0.01414016',                // Quantity string
         'price_str': '12700.00',                   // Price string
         'timestamp': '1562650233',                 // Event time
         'price': Decimal('12700.0'),               // Price
         'type': 1,
         'id': 93215787
         },
         'event': 'trade',
         'channel': 'live_trades_btcusd'
        }
        """
        data = msg['data']
        chan = msg['channel']
        pair = self.exchange_symbol_to_std_symbol(chan.split('_')[-1])

        t = Trade(
            self.id,
            pair,
            BUY if data['type'] == 0 else SELL,
            Decimal(data['amount']),
            Decimal(data['price']),
            self.timestamp_normalize(int(data['microtimestamp'])),
            id=str(data['id']),
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)
        if 'bts' in msg['event']:
            if msg['event'] == 'bts:connection_established':
                pass
            elif msg['event'] == 'bts:subscription_succeeded':
                pass
            elif msg['event'] == 'bts:request_reconnect':
                LOG.info('%s: exchange maintenance - reconnecting', self.id)
                await conn.close()
            else:
                LOG.warning("%s: Unexpected message %s", self.id, msg)
        elif msg['event'] == 'trade':
            await self._trades(msg, timestamp)
        elif msg['event'] == 'data':
            if msg['channel'].startswith('detail_order_book'):
                await self._process_l3_book(msg, timestamp)
            elif msg['channel'].startswith('order_book'):
                await self._process_l2_book(msg, timestamp)
            else:
                LOG.warning('%s: unexpected data channel %s', self.id, msg['channel'])
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    def _snapshot_url(self, symbol: str) -> str:
        return self.rest_endpoints[0].route('l2book', self.sandbox).format(symbol)

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        r = json.loads(data, parse_float=Decimal)
        book = OrderBook(self.id, symbol, max_depth=self.max_depth, asks={Decimal(u[0]): Decimal(u[1]) for u in r['asks']}, bids={Decimal(u[0]): Decimal(u[1]) for u in r['bids']})
        book.timestamp = float(r['timestamp'])
        book.sequence_number = int(r['microtimestamp'])
        book.raw = r
        return book

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                await conn.write(
                    json.dumps({
                        "event": "bts:subscribe",
                        "data": {
                            "channel": f"{chan}_{pair}"
                        }
                    }))

