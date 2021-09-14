'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, FUNDING, FUTURES, KRAKEN_FUTURES, L2_BOOK, OPEN_INTEREST, PERPETUAL, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Ticker, Funding, OpenInterest


LOG = logging.getLogger('feedhandler')


class KrakenFutures(Feed):
    id = KRAKEN_FUTURES
    symbol_endpoint = 'https://futures.kraken.com/derivatives/api/v3/instruments'
    websocket_channels = {
        L2_BOOK: 'book',
        TRADES: 'trade',
        TICKER: 'ticker_lite',
        FUNDING: 'ticker',
        OPEN_INTEREST: 'ticker',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        _kraken_futures_product_type = {
            'FI': 'Inverse Futures',
            'FV': 'Vanilla Futures',
            'PI': 'Perpetual Inverse Futures',
            'PV': 'Perpetual Vanilla Futures',
            'IN': 'Real Time Index',
            'RR': 'Reference Rate',
        }
        ret = {}
        info = defaultdict(dict)

        data = data['instruments']
        for entry in data:
            if not entry['tradeable']:
                continue
            ftype, symbol = entry['symbol'].upper().split("_", maxsplit=1)
            stype = PERPETUAL
            expiry = None
            if "_" in symbol:
                stype = FUTURES
                symbol, expiry = symbol.split("_")
            symbol = symbol.replace('XBT', 'BTC')
            base, quote = symbol[:3], symbol[3:]

            s = Symbol(base, quote, type=stype, expiry_date=expiry)

            info['tick_size'][s.normalized] = entry['tickSize']
            info['contract_size'][s.normalized] = entry['contractSize']
            info['underlying'][s.normalized] = entry['underlying']
            info['product_type'][s.normalized] = _kraken_futures_product_type[ftype]
            info['instrument_type'][s.normalized] = stype
            ret[s.normalized] = entry['symbol']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://futures.kraken.com/ws/v1', **kwargs)
        self.__reset()

    def __reset(self):
        self._open_interest_cache = {}
        self._l2_book = {}
        self.seq_no = {}

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            await conn.write(json.dumps(
                {
                    "event": "subscribe",
                    "feed": chan,
                    "product_ids": self.subscription[chan]
                }
            ))

    async def _trade(self, msg: dict, pair: str, timestamp: float):
        """
        {
            "feed": "trade",
            "product_id": "PI_XBTUSD",
            "uid": "b5a1c239-7987-4207-96bf-02355a3263cf",
            "side": "sell",
            "type": "fill",
            "seq": 85423,
            "time": 1565342712903,
            "qty": 1135.0,
            "price": 11735.0
        }
        """
        t = Trade(
            self.id,
            pair,
            BUY if msg['side'] == 'buy' else SELL,
            Decimal(msg['qty']),
            Decimal(msg['price']),
            self.timestamp_normalize(msg['time']),
            id=msg['uid'],
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def _ticker(self, msg: dict, pair: str, timestamp: float):
        """
        {
            "feed": "ticker_lite",
            "product_id": "PI_XBTUSD",
            "bid": 11726.5,
            "ask": 11732.5,
            "change": 0.0,
            "premium": -0.1,
            "volume": "7.0541503E7",
            "tag": "perpetual",
            "pair": "XBT:USD",
            "dtm": -18117,
            "maturityTime": 0
        }
        """
        t = Ticker(self.id, pair, msg['bid'], msg['ask'], None, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _book_snapshot(self, msg: dict, pair: str, timestamp: float):
        """
        {
            "feed": "book_snapshot",
            "product_id": "PI_XBTUSD",
            "timestamp": 1565342712774,
            "seq": 30007298,
            "bids": [
                {
                    "price": 11735.0,
                    "qty": 50000.0
                },
                ...
            ],
            "asks": [
                {
                    "price": 11739.0,
                    "qty": 47410.0
                },
                ...
            ],
            "tickSize": null
        }
        """
        bids = {Decimal(update['price']): Decimal(update['qty']) for update in msg['bids']}
        asks = {Decimal(update['price']): Decimal(update['qty']) for update in msg['asks']}
        if pair in self._l2_book:
            self._l2_book[pair].book.bids = bids
            self._l2_book[pair].book.asks = asks
        else:
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks)
        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg, sequence_number=msg['seq'])

    async def _book(self, msg: dict, pair: str, timestamp: float):
        """
        Message is received for every book update:
        {
            "feed": "book",
            "product_id": "PI_XBTUSD",
            "side": "sell",
            "seq": 30007489,
            "price": 11741.5,
            "qty": 10000.0,
            "timestamp": 1565342713929
        }
        """
        if pair in self.seq_no and self.seq_no[pair] + 1 != msg['seq']:
            raise MissingSequenceNumber
        self.seq_no[pair] = msg['seq']

        delta = {BID: [], ASK: []}
        s = BID if msg['side'] == 'buy' else ASK
        price = Decimal(msg['price'])
        amount = Decimal(msg['qty'])

        if amount == 0:
            delta[s].append((price, 0))
            del self._l2_book[pair].book[s][price]
        else:
            delta[s].append((price, amount))
            self._l2_book[pair].book[s][price] = amount

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, delta=delta, sequence_number=msg['seq'], raw=msg)

    async def _funding(self, msg: dict, pair: str, timestamp: float):
        if 'funding_rate' in msg:
            f = Funding(
                self.id,
                pair,
                None,
                msg['funding_rate'],
                self.timestamp_normalize(msg['next_funding_rate_time']),
                self.timestamp_normalize(msg['time']),
                predicted_rate=msg['funding_rate_prediction'],
                raw=msg
            )
            await self.callback(FUNDING, f, timestamp)

        oi = msg['openInterest']
        if pair in self._open_interest_cache and oi == self._open_interest_cache[pair]:
            return
        self._open_interest_cache[pair] = oi
        o = OpenInterest(
            self.id,
            pair,
            oi,
            self.timestamp_normalize(msg['time']),
            raw=msg
        )
        await self.callback(OPEN_INTEREST, o, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            if msg['event'] == 'info':
                return
            elif msg['event'] == 'subscribed':
                return
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            # As per Kraken support: websocket product_id is uppercase version of the REST API symbols
            pair = self.exchange_symbol_to_std_symbol(msg['product_id'].lower())
            if msg['feed'] == 'trade':
                await self._trade(msg, pair, timestamp)
            elif msg['feed'] == 'trade_snapshot':
                return
            elif msg['feed'] == 'ticker_lite':
                await self._ticker(msg, pair, timestamp)
            elif msg['feed'] == 'ticker':
                await self._funding(msg, pair, timestamp)
            elif msg['feed'] == 'book_snapshot':
                await self._book_snapshot(msg, pair, timestamp)
            elif msg['feed'] == 'book':
                await self._book(msg, pair, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
