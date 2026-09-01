'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from cryptofeed.symbols import Symbol, str_to_symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple, Union
from datetime import datetime as dt
import re

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, BYBIT, CANDLES, FUNDING, L2_BOOK, LIQUIDATIONS, SELL, TRADES, OPEN_INTEREST, INDEX, FUTURES, PERPETUAL, SPOT, TICKER
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Index, OpenInterest, Funding, Candle, Liquidation, Ticker

LOG = logging.getLogger(__name__)


DERIVATIVE_TYPES = (FUTURES, PERPETUAL)


def _is_linear(symbol) -> bool:
    """A linear contract settles in the quote currency - USDT or USDC on Bybit."""
    return symbol.type in DERIVATIVE_TYPES and symbol.quote != 'USD'


def _is_inverse(symbol) -> bool:
    """An inverse contract is coin-margined and quoted in USD: BTCUSD, not BTCUSDT."""
    return symbol.type in DERIVATIVE_TYPES and symbol.quote == 'USD'


class Bybit(Feed):
    id = BYBIT
    provides_sequence_number = True
    websocket_channels = {
        L2_BOOK: '',  # Assigned in self.subscribe
        TRADES: 'publicTrade',
        INDEX: 'index',
        OPEN_INTEREST: 'open_interest',
        FUNDING: 'funding',
        CANDLES: 'kline',
        LIQUIDATIONS: 'allLiquidation',
        TICKER: 'tickers'
    }

    _derivative_channels = (websocket_channels[L2_BOOK], websocket_channels[TRADES], websocket_channels[INDEX],
                            websocket_channels[OPEN_INTEREST], websocket_channels[FUNDING],
                            websocket_channels[CANDLES], websocket_channels[LIQUIDATIONS], websocket_channels[TICKER])
    websocket_endpoints = [
        WebsocketEndpoint('wss://stream.bybit.com/v5/public/linear', instrument_filter=_is_linear, channel_filter=_derivative_channels, sandbox='wss://stream-testnet.bybit.com/v5/public/linear', options={'compression': None}),
        WebsocketEndpoint('wss://stream.bybit.com/v5/public/inverse', instrument_filter=_is_inverse, channel_filter=_derivative_channels, sandbox='wss://stream-testnet.bybit.com/v5/public/inverse', options={'compression': None}),
        # note the trailing comma - ('TYPE', (SPOT)) is a substring test against the string 'spot'
        WebsocketEndpoint('wss://stream.bybit.com/v5/public/spot', instrument_filter=('TYPE', (SPOT,)), channel_filter=(websocket_channels[L2_BOOK], websocket_channels[TRADES], websocket_channels[CANDLES], websocket_channels[TICKER]), sandbox='wss://stream-testnet.bybit.com/v5/public/spot', options={'compression': None}),
    ]
    rest_endpoints = [
        RestEndpoint('https://api.bybit.com', routes=Routes(['/v5/market/instruments-info?&category=linear&status=Trading&limit=1000', '/v5/market/instruments-info?&category=inverse&status=Trading&limit=1000', '/v5/market/instruments-info?&category=spot&status=Trading&limit=1000']))
    ]
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '1d', '1w', '1M'}
    candle_interval_map = {'1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '2h': '120', '4h': '240', '6h': '360', '1d': 'D', '1w': 'W', '1M': 'M'}

    # Bybit sends delta updates for futures, which might not include some values if they haven't changed.
    # https://bybit-exchange.github.io/docs/v5/websocket/public/ticker
    # Initialize the store to keep snapshots and update the data with deltas
    tickers = {}

    @classmethod
    def timestamp_normalize(cls, ts: Union[int, str, dt]) -> float:
        if isinstance(ts, int):
            return ts / 1000.0
        if isinstance(ts, str):
            ts = dt.fromisoformat(ts)
        return ts.timestamp()

    @staticmethod
    def convert_to_spot_name(cls, pair):
        # Bybit spot and USDT perps use the same symbol name. To distinguish them, use a slash to separate the base and quote.
        if not re.findall(r"(USDT|USDC|EUR|BTC|ETH|DAI|BRZ)$", pair):
            LOG.error("Quote currency not found in the trading pair %s", pair)

            return None

        return re.sub(r"(USDT|USDC|EUR|BTC|ETH|DAI|BRZ)$", r"/\1", pair)

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for msg in data:
            if isinstance(msg['result'], dict):
                for symbol in msg['result']['list']:
                    contract_type = symbol.get('contractType')
                    if not contract_type:
                        stype = SPOT
                    elif contract_type in ('LinearPerpetual', 'InversePerpetual'):
                        stype = PERPETUAL
                    elif contract_type in ('LinearFutures', 'InverseFutures'):
                        stype = FUTURES
                    else:
                        cls.unsupported_category('contractType', contract_type)
                        continue

                    base = symbol['baseCoin']
                    quote = symbol['quoteCoin']

                    expiry = None

                    if stype is FUTURES:
                        if '-' in symbol['symbol']:
                            # linear futures carry the date in the symbol: BTCUSDT-14AUG26
                            expiry = symbol['symbol'].split('-')[-1]
                        elif symbol.get('deliveryTime', '0') != '0':
                            # inverse futures do not (BTCUSDU26), so take the delivery timestamp.
                            # Without this they reached Symbol() with no expiry and it raised.
                            expiry = int(symbol['deliveryTime']) / 1000

                    s = Symbol(base, quote, type=stype, expiry_date=expiry)

                    # Bybit spot and USDT perps share the same symbol name, so
                    # here it is formed using the base and quote coins, separated
                    # by a slash. This is consistent with the UI.
                    # https://bybit-exchange.github.io/docs/v5/enum#symbol
                    if stype == SPOT:
                        ret[s.normalized] = f'{base}/{quote}'
                    elif stype == PERPETUAL and symbol['symbol'].endswith('PERP'):
                        ret[s.normalized] = symbol['symbol']
                    elif stype == PERPETUAL:
                        ret[s.normalized] = f'{base}{quote}'
                    elif stype == FUTURES:
                        ret[s.normalized] = symbol['symbol']

                    info['tick_size'][s.normalized] = Decimal(symbol['priceFilter']['tickSize'])
                    info['instrument_type'][s.normalized] = stype

        return ret, info

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

        for _, pairs in conn.subscription.items():
            for pair in pairs:
                symbol = self.exchange_symbol_to_std_symbol(pair)
                self.tickers.pop(symbol, None)

    async def _candle(self, msg: dict, timestamp: float, market: str):
        """
        {
            "topic": "kline.5.BTCPERP",
            "data": [
                {
                    "start": 1671187800000,
                    "end": 1671188099999,
                    "interval": "5",
                    "open": "16991",
                    "close": "16980.5",
                    "high": "16991",
                    "low": "16980.5",
                    "volume": "2.501",
                    "turnover": "42493.2305",
                    "confirm": false,
                    "timestamp": 1671187815755
                }
            ],
            "ts": 1671187815755,
            "type": "snapshot"
        }
        """
        symbol = msg['topic'].split(".")[-1]
        if market == 'spot':
            symbol = self.convert_to_spot_name(self, symbol)
            if not symbol:
                return

        symbol = self.exchange_symbol_to_std_symbol(symbol)

        ts = int(msg['ts'])

        for entry in msg['data']:
            if self.candle_closed_only and not entry['confirm']:
                continue
            c = Candle(self.id,
                       symbol,
                       self.timestamp_normalize(entry['start']),
                       self.timestamp_normalize(entry['end']),
                       self.candle_interval,
                       None,
                       Decimal(entry['open']),
                       Decimal(entry['close']),
                       Decimal(entry['high']),
                       Decimal(entry['low']),
                       Decimal(entry['volume']),
                       entry['confirm'],
                       self.timestamp_normalize(ts),
                       raw=entry)
            await self.callback(CANDLES, c, timestamp)

    async def _liquidation(self, msg: dict, timestamp: float):
        '''
        {
            "topic": "allLiquidation.ROSEUSDT",
            "type": "snapshot",
            "ts": 1739502303204,
            "data": [
                {
                    "T": 1739502302929,
                    "s": "ROSEUSDT",
                    "S": "Sell",          # side of the liquidated position
                    "v": "20000",         # executed size
                    "p": "0.04499"        # bankruptcy price
                }
            ]
        }
        '''
        for entry in msg['data']:
            liq = Liquidation(
                self.id,
                self.exchange_symbol_to_std_symbol(entry['s']),
                BUY if entry['S'] == 'Buy' else SELL,
                Decimal(entry['v']),
                Decimal(entry['p']),
                None,
                None,
                self.timestamp_normalize(entry['T']),
                raw=entry
            )
            await self.callback(LIQUIDATIONS, liq, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        # Bybit spot and USDT perps share the same symbol name, so to help to distinguish spot pairs from USDT perps,
        # pick the market from the WebSocket address URL and pass it to the functions.
        # 'linear' - futures, perpetual, 'spot' - spot
        market = conn.address.split('/')[-1]
        if "success" in msg:
            if msg['success']:
                if msg['op'] == 'subscribe':
                    # {"success": true, "ret_msg": "","op": "subscribe","conn_id": "cejreassvfrsfvb9v1a0-2m"}
                    LOG.debug("%s: Subscribed to channel.", conn.uuid)
                else:
                    LOG.warning("%s: Unhandled 'successs' message received", conn.uuid)
            else:
                LOG.error("%s: Error from exchange %s", conn.uuid, msg)
        elif msg["topic"].startswith('publicTrade'):
            await self._trade(msg, timestamp, market)
        elif msg["topic"].startswith('orderbook'):
            await self._book(msg, timestamp, market)
        elif msg['topic'].startswith('kline'):
            await self._candle(msg, timestamp, market)
        elif msg['topic'].startswith('allLiquidation'):
            await self._liquidation(msg, timestamp)
        elif msg['topic'].startswith('tickers'):
            await self._ticker_open_interest_funding_index(msg, timestamp, conn, market)
        else:
            LOG.warning("%s: Unhandled message type %s", conn.uuid, msg)

    async def subscribe(self, connection: AsyncConnection):
        self.__reset(connection)

        ticker_channels = {self.websocket_channels[c] for c in (TICKER, OPEN_INTEREST, FUNDING, INDEX)}
        tickers_pairs = set()
        for chan, pairs in connection.subscription.items():
            if chan in ticker_channels:
                tickers_pairs.update(pairs)
        if tickers_pairs:
            args = [f"tickers.{pair.replace('/', '')}" for pair in sorted(tickers_pairs)]
            await connection.write(json.dumps({"op": "subscribe", "args": args}))

        for chan, pairs in connection.subscription.items():
            if chan in ticker_channels:
                continue
            std_chan = self.exchange_channel_to_std(chan)
            for pair in pairs:
                sym = str_to_symbol(self.exchange_symbol_to_std_symbol(pair))
                if sym.type == SPOT:
                    pair = pair.replace('/', '')

                if std_chan == CANDLES:
                    topic = f"{self.websocket_channels[CANDLES]}.{self.candle_interval_map[self.candle_interval]}.{pair}"
                elif std_chan == L2_BOOK:
                    topic = f"orderbook.200.{pair}"
                else:
                    topic = f"{chan}.{pair}"

                await connection.write(json.dumps({"op": "subscribe", "args": [topic]}))

    async def _trade(self, msg: dict, timestamp: float, market: str):
        """
        {
        "topic": "publicTrade.BTCUSDT",
        "type": "snapshot",
        "ts": 1672304486868,
        "data": [
            {
                "T": 1672304486865,
                "s": "BTCUSDT",
                "S": "Buy",
                "v": "0.001",
                "p": "16578.50",
                "L": "PlusTick",
                "i": "20f43950-d8dd-5b31-9112-a178eb6023af",
                "BT": false}]}
        """
        data = msg['data']
        if isinstance(data, list):
            for trade in data:
                symbol = trade['s']

                if market == 'spot':
                    symbol = self.convert_to_spot_name(self, trade['s'])
                    if not symbol:
                        return

                ts = int(trade['T']) if isinstance(trade['T'], str) else trade['T']

                t = Trade(
                    self.id,
                    self.exchange_symbol_to_std_symbol(symbol),
                    BUY if trade['S'] == 'Buy' else SELL,
                    Decimal(trade['v']),
                    Decimal(trade['p']),
                    self.timestamp_normalize(ts),
                    id=trade['i'],
                    raw=trade
                )
                await self.callback(TRADES, t, timestamp)

    async def _book(self, msg: dict, timestamp: float, market: str):
        '''
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "snapshot",
            "ts": 1672304484978,
            "data": {
                "s": "BTCUSDT",
                "b": [
                    ...,
                    [
                        "16493.50",
                        "0.006"
                    ],
                    [
                        "16493.00",
                        "0.100"
                    ]
                ],
                "a": [
                    [
                        "16611.00",
                        "0.029"
                    ],
                    [
                        "16612.00",
                        "0.213"
                    ],
                    ...,
                ],
            "u": 18521288,
            "seq": 7961638724
            }
            "cts": 1672304484976
        }
        '''
        pair = msg['topic'].split('.')[-1]
        update_type = msg['type']
        data = msg['data']
        delta = {BID: [], ASK: []}

        if market == 'spot':
            pair = self.convert_to_spot_name(self, data['s'])
            if not pair:
                return

        pair = self.exchange_symbol_to_std_symbol(pair)

        if update_type == 'snapshot':
            delta = None
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
        elif pair not in self._l2_book:
            return

        for key, update in data.items():
            side = BID if key == 'b' else ASK
            if key == 'a' or key == 'b':
                for price, size in update:
                    price = Decimal(price)
                    size = Decimal(size)
                    if delta is not None:
                        delta[side].append((price, size))

                    if size == 0:
                        if price in self._l2_book[pair].book[side]:
                            del self._l2_book[pair].book[side][price]
                    else:
                        self._l2_book[pair].book[side][price] = size

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(int(msg['ts'])), raw=msg, delta=delta, sequence_number=data.get('u'))

    async def _ticker_open_interest_funding_index(self, msg: dict, timestamp: float, conn: AsyncConnection, market: str):
        '''
        {
            "topic": "tickers.BTCUSDT",
            "type": "snapshot",
            "data": {
                "symbol": "BTCUSDT",
                "tickDirection": "PlusTick",
                "price24hPcnt": "0.017103",
                "lastPrice": "17216.00",
                "prevPrice24h": "16926.50",
                "highPrice24h": "17281.50",
                "lowPrice24h": "16915.00",
                "prevPrice1h": "17238.00",
                "markPrice": "17217.33",
                "indexPrice": "17227.36",
                "openInterest": "68744.761",
                "openInterestValue": "1183601235.91",
                "turnover24h": "1570383121.943499",
                "volume24h": "91705.276",
                "nextFundingTime": "1673280000000",
                "fundingRate": "-0.000212",
                "bid1Price": "17215.50",
                "bid1Size": "84.489",
                "ask1Price": "17216.00",
                "ask1Size": "83.020"
            },
            "cs": 24987956059,
            "ts": 1673272861686
        }
        '''

        # Bybit does not provide bid/ask information for the spot market, only for perps at the moment
        update_type = msg['type']
        update = msg['data']
        _pair = msg['data']['symbol']
        if market == 'spot':
            _pair = self.convert_to_spot_name(self, _pair)
            if not _pair:
                return
        symbol = self.exchange_symbol_to_std_symbol(_pair)

        if update_type == 'snapshot' or symbol not in self.tickers:
            self.tickers[symbol] = dict(update)
        else:
            self.tickers[symbol].update(update)
        update = self.tickers[symbol]

        if self.websocket_channels[TICKER] in conn.subscription and _pair in conn.subscription[self.websocket_channels[TICKER]]:
            t = Ticker(
                self.id,
                symbol,
                Decimal(update['bid1Price']) if 'bid1Price' in update else Decimal(0),
                Decimal(update['ask1Price']) if 'ask1Price' in update else Decimal(0),
                self.timestamp_normalize(int(msg['ts'])),
                raw=update
            )
            await self.callback(TICKER, t, timestamp)

        if (self.websocket_channels[FUNDING] in conn.subscription and _pair in conn.subscription[self.websocket_channels[FUNDING]] and 'markPrice' in update and update.get('fundingRate')):
            f = Funding(
                self.id,
                symbol,
                Decimal(update['markPrice']),
                Decimal(update['fundingRate']),
                self.timestamp_normalize(int(update['nextFundingTime'])) if update.get('nextFundingTime') else None,
                self.timestamp_normalize(int(msg['ts'])),
                None,
                raw=update
            )
            await self.callback(FUNDING, f, timestamp)

        if self.websocket_channels[OPEN_INTEREST] in conn.subscription and _pair in conn.subscription[self.websocket_channels[OPEN_INTEREST]] and 'openInterest' in update:
            o = OpenInterest(
                self.id,
                symbol,
                Decimal(update['openInterest']),
                self.timestamp_normalize(int(msg['ts'])),
                raw=update
            )

            await self.callback(OPEN_INTEREST, o, timestamp)

        if self.websocket_channels[INDEX] in conn.subscription and _pair in conn.subscription[self.websocket_channels[INDEX]] and 'indexPrice' in update:
            i = Index(
                self.id,
                symbol,
                Decimal(update['indexPrice']),
                self.timestamp_normalize(int(msg['ts'])),
                raw=update
            )

            await self.callback(INDEX, i, timestamp)
