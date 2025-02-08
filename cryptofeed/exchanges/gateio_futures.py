'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import logging
from collections import defaultdict
from decimal import Decimal
from yapic import json
import time

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import GATEIO_FUTURES, PERPETUAL, CANDLES, L2_BOOK, TICKER, TRADES, BID, ASK, BUY, SELL, OPEN_INTEREST, INDEX, FUNDING

from cryptofeed.exchanges.gateio import Gateio
from typing import Dict, Tuple
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade, Ticker, Candle, Index, OpenInterest, Funding
from cryptofeed.util.time import timedelta_str_to_sec

LOG = logging.getLogger('feedhandler')


class GateioFutures(Gateio):
    id = GATEIO_FUTURES
    websocket_endpoints = [WebsocketEndpoint('wss://fx-ws.gateio.ws/v4/ws/usdt', options={'compression': None})]
    rest_endpoints = [RestEndpoint('https://api.gateio.ws', routes=Routes('/api/v4/futures/usdt/contracts', l2book='/api/v4/futures/usdt/order_book?contract={}&limit=100&with_id=true'))]

    websocket_channels = {
        L2_BOOK: 'futures.order_book_update',
        TRADES: 'futures.trades',
        TICKER: 'futures.book_ticker',
        CANDLES: 'futures.candlesticks',
        FUNDING: 'futures.tickers',
        OPEN_INTEREST: 'futures.tickers',
        INDEX: 'futures.tickers'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            if entry["in_delisting"] is True:
                continue
            base, quote = entry["name"].split("_")
            s = Symbol(base, quote, type=PERPETUAL)
            ret[s.normalized] = entry['name']
            info['instrument_type'][s.normalized] = s.type
            info['tick_size'][s.normalized] = entry['order_price_round']
        return ret, info

    async def _book_ticker(self, msg: dict, timestamp: float):
        """
        {
        "time": 1615366379,
        "time_ms": 1615366379123,
        "channel": "futures.book_ticker",
        "event": "update",
        "error": null,
        "result": {
            "t": 1615366379123,     // Book ticker generated timestamp in milliseconds
            "u": 2517661076,        // Order book update id
            "s": "BTC_USD",         // Symbol
            "b": "54696.6",         // Best bid price
            "B": 37000,             // Best bid amount
            "a": "54696.7",         // Best ask price
            "A": 47061              // Best ask amount
        }
        }
        """
        t = Ticker(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['result']['s']),
            Decimal(msg['result']['b']),
            Decimal(msg['result']['a']),
            float(msg['result']["t"] / 1000),
            raw=msg
        )

        await self.callback(TICKER, t, timestamp)

    async def _candles(self, msg: dict, timestamp: float):
        """
        {
            "time": 1542162490,
            "time_ms": 1542162490123,
            "channel": "futures.candlesticks",
            "event": "update",
            "error": null,
            "result": [
                {
                "t": 1545129300,
                "v": 27525555,
                "c": "95.4",
                "h": "96.9",
                "l": "89.5",
                "o": "94.3",
                "n": "1m_BTC_USD"
                },
                {
                "t": 1545129300,
                "v": 27525555,
                "c": "95.4",
                "h": "96.9",
                "l": "89.5",
                "o": "94.3",
                "n": "1m_BTC_USD"
                }
            ]
        }
        """
        for entry in msg['result']:
            interval, symbol = entry['n'].split('_', 1)
            c = Candle(
                self.id,
                self.exchange_symbol_to_std_symbol(symbol),
                float(entry['t']),
                float(entry['t']) + timedelta_str_to_sec(interval) - 0.1,
                interval,
                None,
                float(entry['o']),
                float(entry['c']),
                float(entry['h']),
                float(entry['l']),
                float(entry['v']),
                None,
                float(msg['time_ms'] / 1000),
                raw=entry
            )
            await self.callback(CANDLES, c, timestamp)

    async def _snapshot(self, symbol: str):
        """
        {
            "id": 123456,
            "current": 1623898993.123,
            "update": 1623898993.121,
            "asks": [
                {
                "p": "1.52",
                "s": 100
                },
                {
                "p": "1.53",
                "s": 40
                }
            ],
            "bids": [
                {
                "p": "1.17",
                "s": 150
                },
                {
                "p": "1.16",
                "s": 203
                }
            ]
        }
        """
        ret = await self.http_conn.read(self.rest_endpoints[0].route('l2book', self.sandbox).format(symbol))
        data = json.loads(ret, parse_float=Decimal)

        symbol = self.exchange_symbol_to_std_symbol(symbol)
        self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)
        self.last_update_id[symbol] = data['id']

        self._l2_book[symbol].book.bids = {Decimal(bid["p"]): Decimal(bid["s"]) for bid in data['bids']}
        self._l2_book[symbol].book.asks = {Decimal(ask["p"]): Decimal(ask["s"]) for ask in data['asks']}
        # self._l2_book[symbol].book.asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}
        await self.book_callback(L2_BOOK, self._l2_book[symbol], time.time(), raw=data, sequence_number=data['id'])

    async def _process_l2_book(self, msg: dict, timestamp: float):
        """
        {
            "time": 1615366381,
            "time_ms": 1615366381123,
            "channel": "futures.order_book_update",
            "event": "update",
            "error": null,
            "result": {
                "t": 1615366381417,     ms timestamp
                "s": "BTC_USD",         symbol
                "U": 2517661101,        start of update seq no
                "u": 2517661113,        end of update seq no
                "b": [
                {
                    "p": "54672.1",
                    "s": 0
                },
                {
                    "p": "54664.5",
                    "s": 58794
                }
                ],
                "a": [
                {
                    "p": "54743.6",
                    "s": 0
                },
                {
                    "p": "54742",
                    "s": 95
                }
                ]
            }
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['result']['s'])
        if symbol not in self._l2_book:
            await self._snapshot(msg['result']['s'])

        skip_update = self._check_update_id(symbol, msg['result'])
        if skip_update:
            return

        ts = msg['result']['t'] / 1000
        delta = {BID: [], ASK: []}

        for s, side in (('b', BID), ('a', ASK)):
            for update in msg['result'][s]:
                price = Decimal(update["p"])
                amount = Decimal(update["s"])

                if amount == 0:
                    if price in self._l2_book[symbol].book[side]:
                        del self._l2_book[symbol].book[side][price]
                        delta[side].append((price, amount))
                else:
                    self._l2_book[symbol].book[side][price] = amount
                    delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, delta=delta, timestamp=ts, raw=msg)

    async def _trades(self, msg: dict, timestamp: float):
        """
        {
            "channel": "futures.trades",
            "event": "update",
            "time": 1541503698,
            "time_ms": 1541503698123,
            "result": [
                {
                "size": -108,
                "id": 27753479,
                "create_time": 1545136464,
                "create_time_ms": 1545136464123,
                "price": "96.4",
                "contract": "BTC_USD"
                }
            ]
        }
        """
        for entry in msg['result']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(entry['contract']),
                SELL if entry['size'] < 0 else BUY,
                Decimal(abs(entry['size'])),
                Decimal(entry['price']),
                float(entry['create_time_ms'] / 1000),
                id=str(entry['id']),
                raw=entry
            )
            await self.callback(TRADES, t, timestamp)

    async def _tickers(self, msg: dict, timestamp: float):
        """
        {
            "time": 1541"659086,
            "time_ms": 1541659086123,
            "channel": "futures.tickers",
            "event": "update",
            "error": null,
            "result": [
                {
                "contract": "BTC_USD",
                "last": "118.4",
                "change_percentage": "0.77",
                "funding_rate": "-0.000114",
                "funding_rate_indicative": "0.01875",
                "mark_price": "118.35",
                "index_price": "118.36",
                "total_size": "73648",
                "volume_24h": "745487577",
                "volume_24h_btc": "117",
                "volume_24h_usd": "419950",
                "quanto_base_rate": "",
                "volume_24h_quote": "1665006",
                "volume_24h_settle": "178",
                "volume_24h_base": "5526",
                "low_24h": "99.2",
                "high_24h": "132.5"
                }
            ]
        }
        """
        ts = msg['time_ms'] / 1000
        for entry in msg['result']:
            if "total_size" in entry:
                oi = OpenInterest(
                    self.id,
                    self.exchange_symbol_to_std_symbol(entry['contract']),
                    Decimal(entry['total_size']),
                    ts,
                    raw=entry
                )
                await self.callback(OPEN_INTEREST, oi, timestamp)

            if "index_price" in entry:
                i = Index(
                    self.id,
                    self.exchange_symbol_to_std_symbol(entry['contract']),
                    Decimal(entry['index_price']),
                    ts,
                    raw=entry
                )
                await self.callback(INDEX, i, timestamp)

            if "funding_rate" in entry:
                f = Funding(
                    self.id,
                    self.exchange_symbol_to_std_symbol(entry['contract']),
                    Decimal(entry["mark_price"]),
                    Decimal(entry['funding_rate']),
                    None,
                    ts,
                    Decimal(entry['funding_rate_indicative']),
                    raw=entry
                )
                await self.callback(FUNDING, f, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if "error" in msg:
            if msg['error'] is None:
                pass
            else:
                LOG.warning("%s: Error received from exchange - %s", self.id, msg)
        if msg['event'] == 'subscribe':
            return
        elif 'channel' in msg:
            market, channel = msg['channel'].split('.')
            if channel == 'book_ticker':
                await self._book_ticker(msg, timestamp)
            elif channel == 'tickers':
                await self._tickers(msg, timestamp)
            elif channel == 'trades':
                await self._trades(msg, timestamp)
            elif channel == 'order_book_update':
                await self._process_l2_book(msg, timestamp)
            elif channel == 'candlesticks':
                await self._candles(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
