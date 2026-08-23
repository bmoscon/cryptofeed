'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from cryptofeed.symbols import Symbol, Symbols
import logging
from decimal import Decimal
from typing import Dict, Tuple

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, CANDLES, PHEMEX, L2_BOOK, SELL, TRADES, PERPETUAL
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Candle

LOG = logging.getLogger(__name__)


class Phemex(Feed):
    id = PHEMEX
    keepalive_interval = 5.0
    PING_ID = 2

    async def keepalive(self, conn: AsyncConnection):
        await conn.write(json.dumps({'id': self.PING_ID, 'method': 'server.ping', 'params': []}))

    websocket_endpoints = [WebsocketEndpoint('wss://ws.phemex.com', sandbox='wss://testnet-api.phemex.com/ws', limit=20)]
    rest_endpoints = [RestEndpoint('https://api.phemex.com', routes=Routes('/exchange/public/cfg/v2/products'))]
    price_scale = {}
    api_version = {}
    valid_candle_intervals = ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1M', '1Q', '1Y')
    candle_interval_map = {interval: second for interval, second in zip(valid_candle_intervals, [60, 300, 900, 1800, 3600, 14400, 86400, 604800, 2592000, 7776000, 31104000])}

    websocket_channels = {
        L2_BOOK: 'orderbook.subscribe',
        TRADES: 'trade.subscribe',
        CANDLES: 'kline.subscribe',
    }
    v2_websocket_channels = {
        L2_BOOK: 'orderbook_p.subscribe',
        TRADES: 'trade_p.subscribe',
        CANDLES: 'kline_p.subscribe',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1_000_000_000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']['products']:
            if entry['status'] != 'Listed':
                continue
            stype = entry['type'].lower()
            if "perpetual" in stype:    # can be "perpetualv2" or "perpetualpilot"
                stype = PERPETUAL
            base, quote = entry['displaySymbol'].split("/")
            s = Symbol(base.strip(), quote.strip(), type=stype)
            ret[s.normalized] = entry['symbol']
            info['tick_size'][s.normalized] = entry['tickSize'] if 'tickSize' in entry else entry['quoteTickSize']
            info['instrument_type'][s.normalized] = stype

            if stype == PERPETUAL and 'priceScale' not in entry:
                info['api_version'][s.normalized] = 2
            else:
                info['api_version'][s.normalized] = 1
                info['price_scale'][s.normalized] = 10 ** entry.get('priceScale', 8)
        return ret, info

    def _apply_symbol_mapping(self):
        super()._apply_symbol_mapping()
        info = Symbols.get(self.id)[1]
        self.price_scale = {symbol: int(scale) for symbol, scale in info.get('price_scale', {}).items()}
        self.api_version = {symbol: int(version) for symbol, version in info.get('api_version', {}).items()}

    def _subscription_resolved(self):
        # Phemex only allows 5 connections, with 20 subscriptions per connection, check we arent over the limit
        if sum(map(len, self.subscription.values())) > 100:
            raise ValueError(f"{self.id} only allows a maximum of 100 symbol/channel subscriptions")

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

    async def _l2_update(self, symbol: str, levels: dict, snapshot: bool, ts: float, timestamp: float):
        if snapshot:
            delta = None
            self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth, bids=dict(levels[BID]), asks=dict(levels[ASK]))
        else:
            delta = levels
            for side in (ASK, BID):
                for price, amount in levels[side]:
                    if amount == 0:
                        # for some unknown reason deletes can be repeated in book updates
                        if price in self._l2_book[symbol].book[side]:
                            del self._l2_book[symbol].book[side][price]
                    else:
                        self._l2_book[symbol].book[side][price] = amount

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, timestamp=ts, delta=delta)

    async def _book(self, msg: dict, timestamp: float):
        """
        v1 - prices are integers scaled by priceScale, sizes are contracts (inverse) or scaled base
        quantities (spot)

        {
            'book': {
                'asks': [],
                'bids': [
                    [345475000, 14340]
                ]
            },
            'depth': 30,
            'sequence': 9047872983,
            'symbol': 'BTCUSD',
            'timestamp': 1625329629283990943,
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        scale = Decimal(self.price_scale[symbol])
        levels = {BID: [], ASK: []}
        for key, side in (('asks', ASK), ('bids', BID)):
            levels[side] = [(Decimal(price) / scale, Decimal(amount)) for price, amount in msg['book'][key]]

        await self._l2_update(symbol, levels, msg['type'] == 'snapshot', self.timestamp_normalize(msg['timestamp']), timestamp)

    async def _book_p(self, msg: dict, timestamp: float):
        """
        v2 - prices and sizes are decimal strings, no scaling. A size of 0 is a delete, as in v1

        {
            'depth': 30,
            'dts': 1786993351156470977,
            'mts': 1786993351155679251,
            'orderbook_p': {
                'asks': [['64276.6', '0'], ['64280', '0.093']],
                'bids': [['64270.6', '0.233']]
            },
            'sequence': 12903876710,
            'symbol': 'BTCUSDC',
            'timestamp': 1786993351151333998,
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        levels = {BID: [], ASK: []}
        for key, side in (('asks', ASK), ('bids', BID)):
            levels[side] = [(Decimal(price), Decimal(amount)) for price, amount in msg['orderbook_p'][key]]

        await self._l2_update(symbol, levels, msg['type'] == 'snapshot', self.timestamp_normalize(msg['timestamp']), timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        v1

        {
            'sequence': 9047166781,
            'symbol': 'BTCUSD',
            'trades': [
                [1625326381255067545, 'Buy', 345890000, 323]
            ],
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        scale = Decimal(self.price_scale[symbol])
        for ts, side, price, amount in msg['trades']:
            t = Trade(
                self.id,
                symbol,
                BUY if side == 'Buy' else SELL,
                Decimal(amount),
                Decimal(price) / scale,
                self.timestamp_normalize(ts),
                raw=msg
            )
            await self.callback(TRADES, t, timestamp)

    async def _trade_p(self, msg: dict, timestamp: float):
        """
        v2 - same layout as v1, but the price is a decimal string and the size is the base quantity

        {
            'dts': 1786993352252547133,
            'mts': 1786993352250748663,
            'sequence': 66288983930,
            'symbol': 'BTCUSDT',
            'trades_p': [
                [1786993352243530151, 'Sell', '64320.1', '0.006']
            ],
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        for ts, side, price, amount in msg['trades_p']:
            t = Trade(
                self.id,
                symbol,
                BUY if side == 'Buy' else SELL,
                Decimal(amount),
                Decimal(price),
                self.timestamp_normalize(ts),
                raw=msg
            )
            await self.callback(TRADES, t, timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        """
        v1

        {
            'kline': [
                [1625332980, 60, 346285000, 346300000, 346390000, 346300000, 346390000, 49917, 144121225]
            ],
            'sequence': 9048385626,
            'symbol': 'BTCUSD',
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        scale = Decimal(self.price_scale[symbol])

        for entry in msg['kline']:
            ts, _, _, open, high, low, close, volume, _ = entry
            c = Candle(
                self.id,
                symbol,
                ts,
                ts + self.candle_interval_map[self.candle_interval],
                self.candle_interval,
                None,
                Decimal(open) / scale,
                Decimal(close) / scale,
                Decimal(high) / scale,
                Decimal(low) / scale,
                Decimal(volume),
                None,
                None
            )
            await self.callback(CANDLES, c, timestamp)

    async def _candle_p(self, msg: dict, timestamp: float):
        """
        v2 - same layout as v1 (start, interval, last close, open, high, low, close, volume, turnover)
        but every price and size is a decimal string, and the volume is the base quantity

        {
            'dts': 1786993345047502771,
            'kline_p': [
                [1786993320, 60, '64341.6', '64340', '64340', '64320.1', '64320.1', '0.926', '59569.074']
            ],
            'mts': 1786993345045242907,
            'sequence': 66288980129,
            'symbol': 'BTCUSDT',
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])

        for entry in msg['kline_p']:
            ts, _, _, open, high, low, close, volume, _ = entry
            c = Candle(
                self.id,
                symbol,
                ts,
                ts + self.candle_interval_map[self.candle_interval],
                self.candle_interval,
                None,
                Decimal(open),
                Decimal(close),
                Decimal(high),
                Decimal(low),
                Decimal(volume),
                None,
                None
            )
            await self.callback(CANDLES, c, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg.get('id') == self.PING_ID and not msg.get('error'):
            # answers keepalive(); {'error': None, 'id': PING_ID, 'result': {'status': 'success'}}
            return
        elif 'id' in msg and msg['id'] == 1 and not msg['error']:
            pass
        elif 'book' in msg:
            await self._book(msg, timestamp)
        elif 'orderbook_p' in msg:
            await self._book_p(msg, timestamp)
        elif 'trades' in msg:
            await self._trade(msg, timestamp)
        elif 'trades_p' in msg:
            await self._trade_p(msg, timestamp)
        elif 'kline' in msg:
            await self._candle(msg, timestamp)
        elif 'kline_p' in msg:
            await self._candle_p(msg, timestamp)
        elif 'result' in msg:
            if 'error' in msg and msg['error'] is not None:
                LOG.warning("%s: Error from exchange %s", conn.uuid, msg)
                return
            else:
                LOG.warning("%s: Unhandled 'result' message: %s", conn.uuid, msg)
        else:
            LOG.warning("%s: Invalid message type %s", conn.uuid, msg)

    def _method(self, channel: str, symbol: str) -> str:
        std_channel = self.exchange_channel_to_std(channel)
        if self.api_version.get(self.exchange_symbol_to_std_symbol(symbol)) == 2:
            return self.v2_websocket_channels[std_channel]
        return channel

    async def subscribe(self, conn: AsyncConnection):
        self.__reset(conn)

        for chan, symbols in conn.subscription.items():
            for sym in symbols:
                msg = {"id": 1, "method": self._method(chan, sym), "params": [sym]}
                if self.exchange_channel_to_std(chan) == CANDLES:
                    msg['params'] = [sym, self.candle_interval_map[self.candle_interval]]
                LOG.debug(f"{conn.uuid}: Sending subscribe request to public channel: {msg}")
                await conn.write(json.dumps(msg))
