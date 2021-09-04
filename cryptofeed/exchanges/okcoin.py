'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
import logging
import zlib
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import ASK, BID, BUY, L2_BOOK, OKCOIN, SELL, TICKER, TRADES
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade, Ticker

LOG = logging.getLogger('feedhandler')


class OKCoin(Feed):
    id = OKCOIN
    symbol_endpoint = 'https://www.okcoin.com/api/spot/v3/instruments'
    websocket_channels = {
        L2_BOOK: 'spot/depth_l2_tbt',
        TRADES: 'spot/trade',
        TICKER: 'spot/ticker',
    }

    @classmethod
    def timestamp_normalize(cls, ts) -> float:
        return ts.timestamp()

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        for e in data:

            s = Symbol(e['base_currency'], e['quote_currency'])
            ret[s.normalized] = e['instrument_id']
            info['tick_size'][s.normalized] = e['tick_size']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://real.okcoin.com:8443/ws/v3', **kwargs)

    def __reset(self):
        self._l2_book = {}

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        for chan in self.subscription:
            for symbol in self.subscription[chan]:
                request = {"op": "subscribe", "args": f"{chan}:{symbol}"}
                await conn.write(json.dumps(request))

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            'table': 'spot/ticker',
            'data': [
                {
                    'instrument_id': 'BTC-USD',
                    'last': '3977.74',
                    'best_bid': '3977.08',
                    'best_ask': '3978.73',
                    'open_24h': '3978.21',
                    'high_24h': '3995.43',
                    'low_24h': '3961.02',
                    'base_volume_24h': '248.245',
                    'quote_volume_24h': '988112.225861',
                    'timestamp': '2019-03-22T22:26:34.019Z'
                }
            ]
        }
        """
        for update in msg['data']:
            pair = update['instrument_id']
            update_timestamp = self.timestamp_normalize(update['timestamp'])
            t = Ticker(self.id, pair, Decimal(update['best_bid']) if update['best_bid'] else Decimal(0), Decimal(update['best_ask']) if update['best_ask'] else Decimal(0), update_timestamp, raw=update)
            await self.callback(TICKER, t, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {'table': 'spot/trade', 'data': [{'instrument_id': 'BTC-USD', 'price': '3977.44', 'side': 'buy', 'size': '0.0096', 'timestamp': '2019-03-22T22:45:44.578Z', 'trade_id': '486519521'}]}
        """
        for trade in msg['data']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(trade['instrument_id']),
                BUY if trade['side'] == 'buy' else SELL,
                Decimal(trade['size']),
                Decimal(trade['price']),
                self.timestamp_normalize(trade['timestamp']),
                id=trade['trade_id'],
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        if msg['action'] == 'partial':
            # snapshot
            for update in msg['data']:
                pair = self.exchange_symbol_to_std_symbol(update['instrument_id'])
                bids = {Decimal(price): Decimal(amount) for price, amount, *_ in update['bids']}
                asks = {Decimal(price): Decimal(amount) for price, amount, *_ in update['asks']}
                self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, checksum_format='OKCOIN', bids=bids, asks=asks)

                if self.checksum_validation and self._l2_book[pair].book.checksum() != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(update['timestamp']), raw=msg, checksum=update['checksum'] & 0xFFFFFFFF)
        else:
            # update
            for update in msg['data']:
                delta = {BID: [], ASK: []}
                pair = self.exchange_symbol_to_std_symbol(update['instrument_id'])
                for side in ('bids', 'asks'):
                    s = BID if side == 'bids' else ASK
                    for price, amount, *_ in update[side]:
                        price = Decimal(price)
                        amount = Decimal(amount)
                        if amount == 0:
                            if price in self._l2_book[pair].book[s]:
                                delta[s].append((price, 0))
                                del self._l2_book[pair].book[s][price]
                        else:
                            delta[s].append((price, amount))
                            self._l2_book[pair].book[s][price] = amount

                if self.checksum_validation and self._l2_book[pair].book.checksum() != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(update['timestamp']), raw=msg, delta=delta, checksum=update['checksum'] & 0xFFFFFFFF)

    async def _login(self, msg: dict, timestamp: float):
        LOG.debug('%s: Websocket logged in? %s', self.id, msg['success'])

    async def message_handler(self, msg: str, conn, timestamp: float):
        # DEFLATE compression, no header
        msg = zlib.decompress(msg, -15)
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            if msg['event'] == 'error':
                LOG.error("%s: Error: %s", self.id, msg)
            elif msg['event'] == 'subscribe':
                pass
            elif msg['event'] == 'login':
                await self._login(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled event %s", self.id, msg)
        elif 'table' in msg:
            if 'ticker' in msg['table']:
                await self._ticker(msg, timestamp)
            elif 'trade' in msg['table']:
                await self._trade(msg, timestamp)
            elif 'depth_l2_tbt' in msg['table']:
                await self._book(msg, timestamp)
            elif 'spot/order' in msg['table']:
                await self._order(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled message %s", self.id, msg)
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)
