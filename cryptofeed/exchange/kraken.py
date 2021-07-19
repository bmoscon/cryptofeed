'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from functools import partial
import logging
from typing import Callable, Dict, List, Tuple
import zlib

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BUY, CANDLES, KRAKEN, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.standards import normalize_channel
from cryptofeed.util.split import list_by_max_items


LOG = logging.getLogger('feedhandler')


class Kraken(Feed):
    id = KRAKEN
    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '15d'}
    valid_depths = [5, 10, 20, 50, 100, 500, 1000]
    symbol_endpoint = 'https://api.kraken.com/0/public/AssetPairs'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        for symbol in data['result']:
            if 'wsname' not in data['result'][symbol] or '.d' in symbol:
                # https://blog.kraken.com/post/259/introducing-the-kraken-dark-pool/
                # .d is for dark pool symbols
                continue

            base, quote = data['result'][symbol]['wsname'].split("/")

            normalized = f"{base}{symbol_separator}{quote}"
            exch = data['result'][symbol]['wsname']
            normalized = normalized.replace('XBT', 'BTC')
            normalized = normalized.replace('XDG', 'DOG')
            ret[normalized] = exch
        return ret, {}

    def __init__(self, candle_interval='1m', max_depth=1000, **kwargs):
        lookup = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440, '1w': 10080, '15d': 21600}
        self.candle_interval = lookup[candle_interval]
        self.normalize_interval = {value: key for key, value in lookup.items()}
        super().__init__('wss://ws.kraken.com', max_depth=max_depth, **kwargs)

    def __reset(self):
        self.l2_book = {}

    def __calc_checksum(self, pair):
        bid_prices = list(reversed(self.l2_book[pair][BID].keys()))[:10]
        ask_prices = list(self.l2_book[pair][ASK].keys())[:10]

        combined = ""
        for data, side in ((ask_prices, ASK), (bid_prices, BID)):
            sizes = [str(self.l2_book[pair][side][price]).replace('.', '').lstrip('0') for price in data]
            prices = [str(price).replace('.', '').lstrip('0') for price in data]
            combined += ''.join([b for a in zip(prices, sizes) for b in a])

        return str(zlib.crc32(combined.encode()))

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        """
        Per Kraken Tech Support, subscribing to more than 20 symbols in a single request can lead
        to data loss. Furthermore, too many symbols on a single connection can cause data loss as well.
        """
        self.__reset()
        ret = []

        def build(options: list):
            subscribe = partial(self.subscribe, options=options)
            conn = WSAsyncConn(self.address, self.id, **self.ws_defaults)
            return conn, subscribe, self.message_handler, self.authenticate

        for chan in self.subscription:
            symbols = list(self.subscription[chan])
            for subset in list_by_max_items(symbols, 20):
                ret.append(build((chan, subset)))

        return ret

    async def subscribe(self, conn: AsyncConnection, options: Tuple[str, List[str]] = None):
        chan = options[0]
        symbols = options[1]
        sub = {"name": chan}
        if normalize_channel(self.id, chan) == L2_BOOK:
            max_depth = self.max_depth if self.max_depth else 1000
            if max_depth not in self.valid_depths:
                for d in self.valid_depths:
                    if d > max_depth:
                        max_depth = d
                        break

            sub['depth'] = max_depth
        if normalize_channel(self.id, chan) == CANDLES:
            sub['interval'] = self.candle_interval

        await conn.write(json.dumps({
            "event": "subscribe",
            "pair": symbols,
            "subscription": sub
        }))

    async def _trade(self, msg: dict, pair: str, timestamp: float):
        """
        example message:

        [1,[["3417.20000","0.21222200","1549223326.971661","b","l",""]]]
        channel id, price, amount, timestamp, size, limit/market order, misc
        """
        for trade in msg[1]:
            price, amount, server_timestamp, side, order_type, _ = trade
            order_type = 'limit' if order_type == 'l' else 'market'
            await self.callback(TRADES, feed=self.id,
                                symbol=pair,
                                side=BUY if side == 'b' else SELL,
                                amount=Decimal(amount),
                                price=Decimal(price),
                                order_id=None,
                                timestamp=float(server_timestamp),
                                receipt_timestamp=timestamp,
                                order_type=order_type)

    async def _ticker(self, msg: dict, pair: str, timestamp: float):
        """
        [93, {'a': ['105.85000', 0, '0.46100000'], 'b': ['105.77000', 45, '45.00000000'], 'c': ['105.83000', '5.00000000'], 'v': ['92170.25739498', '121658.17399954'], 'p': ['107.58276', '107.95234'], 't': [4966, 6717], 'l': ['105.03000', '105.03000'], 'h': ['110.33000', '110.33000'], 'o': ['109.45000', '106.78000']}]
        channel id, asks: price, wholeLotVol, vol, bids: price, wholeLotVol, close: ...,, vol: ..., VWAP: ..., trades: ..., low: ...., high: ..., open: ...
        """
        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=Decimal(msg[1]['b'][0]),
                            ask=Decimal(msg[1]['a'][0]),
                            timestamp=timestamp,
                            receipt_timestamp=timestamp)

    async def _book(self, msg: dict, pair: str, timestamp: float):
        delta = {BID: [], ASK: []}
        msg = msg[1:-2]

        if 'as' in msg[0]:
            # Snapshot
            self.l2_book[pair] = {BID: sd({
                Decimal(update[0]): Decimal(update[1]) for update in msg[0]['bs']
            }), ASK: sd({
                Decimal(update[0]): Decimal(update[1]) for update in msg[0]['as']
            })}
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, delta, timestamp, timestamp)
        else:
            for m in msg:
                for s, updates in m.items():
                    side = False
                    if s == 'b':
                        side = BID
                    elif s == 'a':
                        side = ASK
                    if side:
                        for update in updates:
                            price, size, *_ = update
                            price = Decimal(price)
                            size = Decimal(size)
                            if size == 0:
                                # Per Kraken's technical support
                                # they deliver erroneous deletion messages
                                # periodically which should be ignored
                                if price in self.l2_book[pair][side]:
                                    del self.l2_book[pair][side][price]
                                    delta[side].append((price, 0))
                            else:
                                delta[side].append((price, size))
                                self.l2_book[pair][side][price] = size
            for side in (BID, ASK):
                while len(self.l2_book[pair][side]) > self.max_depth:
                    del_price = self.l2_book[pair][side].items()[0 if side == BID else -1][0]
                    del self.l2_book[pair][side][del_price]
                    delta[side].append((del_price, 0))

            if self.checksum_validation and 'c' in msg[0] and self.__calc_checksum(pair) != msg[0]['c']:
                raise BadChecksum("Checksum validation on orderbook failed")
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp, timestamp)

    async def _candle(self, msg: list, pair: str, timestamp: float):
        """
        [327,
            ['1621988141.603324',   start
             '1621988160.000000',   end
             '38220.70000',         open
             '38348.80000',         high
             '38220.70000',         low
             '38320.40000',         close
             '38330.59222',         vwap
             '3.23539643',          volume
             42                     count
            ],
        'ohlc-1',
        'XBT/USD']
        """
        start, end, open, high, low, close, _, volume, count = msg[1]
        interval = int(msg[-2].split("-")[-1])
        await self.callback(CANDLES,
                            feed=self.id,
                            symbol=pair,
                            timestamp=start,
                            receipt_timestamp=timestamp,
                            start=float(end) - (interval * 60),
                            stop=float(end),
                            interval=self.normalize_interval[interval],
                            trades=count,
                            open_price=Decimal(open),
                            close_price=Decimal(close),
                            high_price=Decimal(high),
                            low_price=Decimal(low),
                            volume=Decimal(volume),
                            closed=None)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg, list):
            channel, pair = msg[-2:]
            pair = self.exchange_symbol_to_std_symbol(pair)
            if channel == 'trade':
                await self._trade(msg, pair, timestamp)
            elif channel == 'ticker':
                await self._ticker(msg, pair, timestamp)
            elif channel[:4] == 'book':
                await self._book(msg, pair, timestamp)
            elif channel[:4] == 'ohlc':
                await self._candle(msg, pair, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            if msg['event'] == 'heartbeat':
                return
            elif msg['event'] == 'systemStatus':
                return
            elif msg['event'] == 'subscriptionStatus' and msg['status'] == 'subscribed':
                return
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
