'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from cryptofeed.symbols import Symbol

from decimal import Decimal
from itertools import islice
import logging
import zlib
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import ASK, BID, BUY, L2_BOOK, OKCOIN, SELL, TICKER, TRADES
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.util import split


LOG = logging.getLogger('feedhandler')


class OKCoin(Feed):
    id = OKCOIN
    symbol_endpoint = 'https://www.okcoin.com/api/spot/v3/instruments'
    websocket_channels = {
        L2_BOOK: 'spot/depth_l2_tbt',
        TRADES: 'spot/trade',
        TICKER: '{}/ticker',
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
        self.open_interest = {}

    def __calc_checksum(self, pair):
        bid_it = reversed(self._l2_book[pair][BID])
        ask_it = iter(self._l2_book[pair][ASK])

        bids = (f"{bid}:{self._l2_book[pair][BID][bid]}" for bid in bid_it)
        bids = list(islice(bids, 25))
        asks = (f"{ask}:{self._l2_book[pair][ASK][ask]}" for ask in ask_it)
        asks = list(islice(asks, 25))

        if len(bids) == len(asks):
            combined = [val for pair in zip(bids, asks) for val in pair]
        elif len(bids) > len(asks):
            combined = [val for pair in zip(bids[:len(asks)], asks) for val in pair]
            combined += bids[len(asks):]
        else:
            combined = [val for pair in zip(bids, asks[:len(bids)]) for val in pair]
            combined += asks[len(bids):]

        computed = ":".join(combined).encode()
        return zlib.crc32(computed)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        symbol_channels = list(self.get_channel_symbol_combinations())
        LOG.info("%s: Got %r combinations of pairs and channels", self.id, len(symbol_channels))

        if len(symbol_channels) == 0:
            LOG.info("%s: No websocket subscription", self.id)
            return False

        # Avoid error "Max frame length of 65536 has been exceeded" by limiting requests to some args
        for chunk in split.list_by_max_items(symbol_channels, 33):
            LOG.info("%s: Subscribe to %s args from %r to %r", self.id, len(chunk), chunk[0], chunk[-1])
            request = {"op": "subscribe", "args": chunk}
            await conn.write(json.dumps(request))

    @classmethod
    def instrument_type(cls, symbol: str):
        return cls.info()['instrument_type'][symbol]

    def get_channel_symbol_combinations(self):
        for chan in self.subscription:
            for symbol in self.subscription[chan]:
                instrument_type = self.instrument_type(symbol)
                yield f"{chan.format(instrument_type)}:{symbol}"

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {'table': 'spot/ticker', 'data': [{'instrument_id': 'BTC-USD', 'last': '3977.74', 'best_bid': '3977.08', 'best_ask': '3978.73', 'open_24h': '3978.21', 'high_24h': '3995.43', 'low_24h': '3961.02', 'base_volume_24h': '248.245', 'quote_volume_24h': '988112.225861', 'timestamp': '2019-03-22T22:26:34.019Z'}]}
        """
        for update in msg['data']:
            pair = update['instrument_id']
            update_timestamp = self.timestamp_normalize(update['timestamp'])
            await self.callback(TICKER, feed=self.id,
                                symbol=pair,
                                bid=Decimal(update['best_bid']) if update['best_bid'] else Decimal(0),
                                ask=Decimal(update['best_ask']) if update['best_ask'] else Decimal(0),
                                timestamp=update_timestamp,
                                receipt_timestamp=timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {'table': 'spot/trade', 'data': [{'instrument_id': 'BTC-USD', 'price': '3977.44', 'side': 'buy', 'size': '0.0096', 'timestamp': '2019-03-22T22:45:44.578Z', 'trade_id': '486519521'}]}
        """
        for trade in msg['data']:
            if msg['table'] in {'futures/trade', 'option/trade'}:
                amount_sym = 'qty'
            else:
                amount_sym = 'size'
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(trade['instrument_id']),
                                order_id=trade['trade_id'],
                                side=BUY if trade['side'] == 'buy' else SELL,
                                amount=Decimal(trade[amount_sym]),
                                price=Decimal(trade['price']),
                                timestamp=self.timestamp_normalize(trade['timestamp']),
                                receipt_timestamp=timestamp
                                )

    async def _book(self, msg: dict, timestamp: float):
        if msg['action'] == 'partial':
            # snapshot
            for update in msg['data']:
                pair = self.exchange_symbol_to_std_symbol(update['instrument_id'])
                self._l2_book[pair] = {
                    BID: sd({
                        Decimal(price): Decimal(amount) for price, amount, *_ in update['bids']
                    }),
                    ASK: sd({
                        Decimal(price): Decimal(amount) for price, amount, *_ in update['asks']
                    })
                }

                if self.checksum_validation and self.__calc_checksum(pair) != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(self._l2_book[pair], L2_BOOK, pair, True, None, self.timestamp_normalize(update['timestamp']), timestamp)
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
                            if price in self._l2_book[pair][s]:
                                delta[s].append((price, 0))
                                del self._l2_book[pair][s][price]
                        else:
                            delta[s].append((price, amount))
                            self._l2_book[pair][s][price] = amount
                if self.checksum_validation and self.__calc_checksum(pair) != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(self._l2_book[pair], L2_BOOK, pair, False, delta, self.timestamp_normalize(update['timestamp']), timestamp)

    async def _login(self, msg: dict, timestamp: float):
        LOG.info('%s: Websocket logged in? %s', self.id, msg['success'])

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
