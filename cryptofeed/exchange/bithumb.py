'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Tuple, Dict
from collections import defaultdict
import copy

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.symbols import Symbols
from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, BITHUMB, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Bithumb(Feed):
    '''
    Before you use this bithumb implementation, you should know that this is exchange's API is pretty terrible.

    For some unknown reason, bithumb's api_info page lists all their KRW symbols as USDT. Probably because they bought
    the exchange and copied everything but didn't bother to update the reference data.

    We'll just assume that anything USDT is actually KRW. A search on their exchange page
    shows that there is no USDT symbols available. Please be careful when referencing their api_info page
    '''
    id = BITHUMB
    api = "https://api.bithumb.com/public"
    symbol_endpoint = [
        ('https://api.bithumb.com/public/ticker/ALL_BTC', 'BTC'),
        ('https://api.bithumb.com/public/ticker/ALL_KRW', 'KRW')
    ]

    # Override symbol_mapping class method, because this bithumb is a very special case.
    # There is no actual page in the API for reference info.
    # Need to query the ticker endpoint by quote currency for that info
    # To qeury the ticker endpoint, you need to know which quote currency you want. So far, seems like the exhcnage
    # only offers KRW and BTC as quote currencies.
    @classmethod
    def symbol_mapping(cls, symbol_separator='-', refresh=False) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            LOG.debug("%s: reading symbol information from %s", cls.id, cls.symbol_endpoint)
            data = {}
            for ep, quote_curr in cls.symbol_endpoint:
                data[quote_curr] = cls.http_sync.read(ep, json=True, uuid=cls.id)

            syms, info = cls._parse_symbol_data(data, symbol_separator)
            Symbols.set(cls.id, syms, info)
            return syms
        except Exception as e:
            LOG.error("%s: Failed to parse symbol information: %s", cls.id, str(e), exc_info=True)
            raise

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}

        for quote_curr, response in data.items():
            bases = response['data']
            for base_curr in bases.keys():
                if base_curr == 'date':
                    continue
                ret["{}-{}".format(base_curr, quote_curr)] = "{}_{}".format(base_curr, quote_curr)

        return ret, {}

    def __init__(self, **kwargs):
        super().__init__("wss://pubwss.bithumb.com/pub/ws", cross_check=True, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = defaultdict(lambda: {ASK: sd(), BID: sd()})

    async def _trades(self, msg: dict, rtimestamp: float):
        '''
        {
            "type": "transaction",
            "content": {
                "list": [
                    {
                        "symbol": "BTC_KRW", // currency code
                        "buySellGb": "1", // type of contract (1: sale contract, 2: buy contract)
                        "contPrice": "10579000", // execution price
                        "contQty": "0.01", // number of contracts
                        "contAmt": "105790.00", // execution amount
                        "contDtm": "2020-01-29 12:24:18.830039", // Signing time
                        "updn": "dn" // comparison with the previous price: up-up, dn-down
                    }
                ]
            }
        }
        '''
        trades = msg.get('content', {}).get('list', [])

        for trade in trades:
            # API ref list uses '-', but market data returns '_'
            symbol = self.exchange_symbol_to_std_symbol(trade['symbol'])
            timestamp = timestamp_normalize(self.id, trade['contDtm'])
            price = Decimal(trade['contPrice'])
            quantity = Decimal(trade['contQty'])
            side = BUY if trade['buySellGb'] == '2' else SELL

            await self.callback(TRADES, feed=self.id,
                                symbol=symbol,
                                side=side,
                                amount=quantity,
                                price=price,
                                order_id=None,
                                timestamp=timestamp,
                                receipt_timestamp=rtimestamp)

    async def _l2_update(self, msg: dict, rtimestamp: float):
        '''
        WARNING: API provides no way to synchronize from a REST snapshot,
        nor does it provide a snapshot via REST. This implementation builds an
        orderbook solely from deltas, and is likely to take some time to
        build an accurate state.
        {
            "type": "orderbookdepth",
            "content": {
                "list": [
                    {
                        "symbol": "BTC_KRW",
                        "orderType": "ask", // order type-bid / ask
                        "price": "10593000", // quote
                        "quantity": "1.11223318", // balance
                        "total": "3" // number of cases
                    },
                    {"symbol": "BTC_KRW", "orderType": "ask", "price": "10596000", "quantity": "0.5495", "total": "8"},
                    {"symbol": "BTC_KRW", "orderType": "ask", "price": "10598000", "quantity": "18.2085", "total": "10"},
                    {"symbol": "BTC_KRW", "orderType": "bid", "price": "10532000", "quantity": "0", "total": "0"},
                    {"symbol": "BTC_KRW", "orderType": "bid", "price": "10572000", "quantity": "2.3324", "total": "4"},
                    {"symbol": "BTC_KRW", "orderType": "bid", "price": "10571000", "quantity": "1.469", "total": "3"},
                    {"symbol": "BTC_KRW", "orderType": "bid", "price": "10569000", "quantity": "0.5152", "total": "2"}
                ],
                "datetime":1580268255864325 // date and time
            }
        }
        '''
        depths = msg.get('content', {}).get('list', [])
        timestamp = msg.get('content', {}).get('datetime', None)

        if len(depths) > 0:
            # API ref list uses '-', but market data returns '_'
            # assume that all depths in the same msg belong to the same symbol
            symbol = self.exchange_symbol_to_std_symbol(depths[0]['symbol'])

            # Copy over so that book_callback can generate deltas.
            self.previous_book[symbol] = copy.deepcopy(self.l2_book[symbol])

            for depth in depths:
                price = Decimal(depth['price'])
                quantity = Decimal(depth['quantity'])
                side = BID if depth['orderType'] == 'bid' else ASK

                if quantity == 0:
                    self.l2_book[symbol][side].pop(price, None)
                else:
                    self.l2_book[symbol][side][price] = quantity

            # Bithumb REST orderbooks only show/retain 30 levels, drop
            # everything past 30 levels
            for book_side, pop_index in ((BID, 0), (ASK, -1)):
                book = self.l2_book[symbol][book_side]
                while len(book) > 30:
                    book.popitem(pop_index)

            await self.book_callback(self.l2_book[symbol], L2_BOOK, symbol, False, None, timestamp, rtimestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        msg_type = msg.get('type', None)

        if msg_type == 'transaction':
            await self._trades(msg, timestamp)
        elif msg_type == 'orderbookdepth':
            await self._l2_update(msg, timestamp)
        elif msg_type is None and msg.get('status', None) == '0000':
            return
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        if self.subscription:
            for chan in self.subscription:
                await conn.write(json.dumps({
                    "type": chan,
                    "symbols": [symbol for symbol in self.subscription[chan]]
                    # API ref list uses '-', but subscription requires '_'
                }))
