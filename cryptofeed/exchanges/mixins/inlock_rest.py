'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
from typing import Dict, Tuple
from datetime import datetime, timezone

from yapic import json

from cryptofeed.defines import L2_BOOK, TICKER, TRADES
from cryptofeed.exceptions import UnexpectedMessage
from cryptofeed.exchange import RestExchange
from cryptofeed.types import OrderBook, Ticker


LOG = logging.getLogger('feedhandler')


class InlockRestMixin(RestExchange):
    api = "https://api.inlock.io/inlock/api/v1.0"
    rest_channels = (L2_BOOK, TICKER)
    # REST API Doc: https://app.swaggerhub.com/apis/IncomeLocker/Inlock_Public_Tokenmarket_API/

    async def _get(self, command: str, retry_count, retry_delay, params=''):
        api = self.api if not self.sandbox else self.sandbox_api
        resp = await self.http_conn.read(f"{api}{command}{params}", retry_count=retry_count, retry_delay=retry_delay)
        return json.loads(resp, parse_float=Decimal)


    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        """
          "ticker_id": "ILK_USDC",
          "timestamp": 1667483423,
          "bids": [
            [
             "0.00684842",
             "12284.00738896"
            ]
                  ]
          "asks": [
            [
             "0.00743366",
            "13586.56156355"
            ]
                 ]
        """

        ret = OrderBook(self.id, symbol)
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self._get(f"/public/tokenmarket/orderbook?ticker_id={sym}&depth=0", retry_count, retry_delay)
        ret.book.bids = {Decimal(u[0]): Decimal(u[1]) for u in data['bids']}
        ret.book.asks = {Decimal(u[0]): Decimal(u[1]) for u in data['asks']}
        return ret


    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        """
        {
            "ticker_id": "ILK_ETH",
            "base_currency": "ILK",
            "target_currency": "ETH",
            "last_price": "0.00000509",
            "base_volume": "1198.54803",
            "target_volume": "0.00607362",
            "bid": "0.00000441",
            "ask": "0.00000509",
            "high": "0.00000509",
            "low": "0.00000503"
        },
        """

        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self._get(f'/public/tokenmarket/tickers', retry_count=retry_count, retry_delay=retry_delay)

        for data_sym in data:
            if data_sym['ticker_id'] in sym:
                val= data_sym

        return {'symbol': symbol,
                'feed': self.id,
                'bid': val['bid'],
                'ask': val['ask']
                }

