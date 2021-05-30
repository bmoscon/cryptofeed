'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import time
import datetime as dt
from decimal import Decimal
from typing import List, Tuple, Callable, Dict
from functools import partial

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll
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
    symbol_endpoint = 'https://global-openapi.bithumb.pro/market/data/config'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        # doc: https://apidocs.bithumb.com/docs/api_info

        # For some unknown reason, bithumb's api_info page lists all their KRW symbols as USDT.
        # Probably because they bought the exchange and copied everything but didnt bother
        # to update the reference data.
        # We'll just assume that anything USDT is actually KRW. a search on their exchange page
        # shows that there is no USDT symbols available.

        ret = {}

        for entry in data['info']['spotConfig']:
            raw_symbol = entry['symbol']
            fixed_symbol = raw_symbol.replace('USDT', 'KRW')
            ret[fixed_symbol.replace("-", symbol_separator)] = fixed_symbol

        return ret, {}

    def __init__(self, **kwargs):
        super().__init__(None, **kwargs)
        self.rest_endpoint = "https://api.bithumb.com/public"
        self.last_traded_time = 0
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _trades(self, msg: dict, rtimestamp: float, bithumb_symbol: str):
        '''
        {"status":"0000","data":[
            {"transaction_date":"2021-05-30 00:59:26","type":"bid","units_traded":"0.0057","price":"41927000","total":"238983"},
            {"transaction_date":"2021-05-30 00:59:26","type":"bid","units_traded":"0.1377","price":"41931000","total":"5773898"},
            {"transaction_date":"2021-05-30 00:59:27","type":"ask","units_traded":"0.0059","price":"41889000","total":"247145"},
        ]}

        bithumb returns a list of recently made transactions. It's up to us to filter out those which we have
        already processed before.

        The current way of filtering based on transaction_date field will result in some trades being duplicated
        when there are multiple trades happening in the same second.
        '''
        pair = self.exchange_symbol_to_std_symbol(bithumb_symbol)
        for record in msg['data']:
            timestamp = timestamp_normalize(self.id, record['transaction_date'])

            if timestamp < self.last_traded_time:
                continue

            self.last_traded_time = timestamp

            price = Decimal(record['price'])
            quantity = Decimal(record['units_traded'])
            side = BUY if record['type'] == 'bid' else SELL

            # bithumb doesnt provide us with a order_id. create our own based on tsns
            order_id = "%.0f" % (time.time() * 1e9)

            await self.callback(TRADES, feed=self.id,
                                symbol=pair,
                                side=side,
                                amount=quantity,
                                price=price,
                                order_id=order_id,
                                timestamp=timestamp,
                                receipt_timestamp=rtimestamp)

    async def _l2_update(self, msg: dict, timestamp: float, bithumb_symbol: str):
        '''
        Bithumb only sends snapshots

        {"status":"0000","data":{"timestamp":"1622303936985","payment_currency":"KRW","order_currency":"BTC",
        "bids":[
            {"price":"41867000","quantity":"0.2301"},
            {"price":"41865000","quantity":"0.0022"},
            {"price":"41863000","quantity":"0.0076"}],
        "asks":[
            {"price":"41925000","quantity":"0.57632296"},
            {"price":"41927000","quantity":"0.0296"},
            {"price":"41935000","quantity":"0.0288"},
            {"price":"41942000","quantity":"0.0259"}
        ]}}
        '''
        pair = self.exchange_symbol_to_std_symbol(bithumb_symbol)
        levels = msg.get('data', {})
        self.l2_book[pair] = {ASK: sd(), BID: sd()}

        for bithumb_side in ('bids', 'asks'):
            side = BID if bithumb_side == "bids" else ASK
            for level in levels.get(bithumb_side, []):
                price = Decimal(level['price'])
                quantity = Decimal(level['quantity'])

                self.l2_book[pair][side][price] = quantity

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp, timestamp)

    async def message_handler(self, bithumb_symbol: str, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        data = msg['data']

        if isinstance(data, list):
            await self._trades(msg, timestamp, bithumb_symbol)
        elif isinstance(data, dict):
            await self._l2_update(msg, timestamp, bithumb_symbol)

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []

        if self.address:
            ret = super().connect()

        # For bithumb, the trade rest api unfortunately does not return an identifier on which symbol the response
        # is for. Hence, we need to make a HTTPPoll object for each with a partial function to call message_handler
        # L2 rest api has the information, but lets stick to the same way for both to keep it clean
        for chan in set(self.subscription):
            if chan == "orderbook":
                for pair in self.subscription[chan]:
                    addr = f"{self.rest_endpoint}/orderbook/{pair.replace('-', '_')}"
                    ret.append((HTTPPoll([addr], self.id, delay=1, sleep=1.0), self.subscribe, partial(self.message_handler, pair)))
            if chan == "transaction_history":
                for pair in self.subscription[chan]:
                    addr = f"{self.rest_endpoint}/transaction_history/{pair.replace('-', '_')}"
                    ret.append((HTTPPoll([addr], self.id, delay=1, sleep=1.0), self.subscribe, partial(self.message_handler, pair)))
            # Bithumb has a 'ticker' channel, but it provide OHLC-last data, not BBO px.
        return ret

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        if self.subscription:
            for chan in self.subscription:
                for pair in self.subscription[chan]:
                    # bithumb is a fully rest exchange. nothing to do here
                    pass
