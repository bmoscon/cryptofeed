'''
Copyright (C) 2018-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hmac
import time
from collections import defaultdict
from cryptofeed.symbols import Symbol, str_to_symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple, Union
from datetime import datetime as dt
import re

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, BYBIT, CANCELLED, CANCELLING, CANDLES, FAILED, FILLED, FUNDING, L2_BOOK, LIMIT, LIQUIDATIONS, MAKER, MARKET, OPEN, PARTIAL, SELL, SUBMITTING, TAKER, TRADES, OPEN_INTEREST, INDEX, ORDER_INFO, FILLS, FUTURES, PERPETUAL, SPOT, TICKER
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Index, OpenInterest, Funding, OrderInfo, Fill, Candle, Liquidation, Ticker

LOG = logging.getLogger('feedhandler')


class Bybit(Feed):
    id = BYBIT
    websocket_channels = {
        L2_BOOK: '',  # Assigned in self.subscribe
        TRADES: 'publicTrade',
        FILLS: 'execution',
        ORDER_INFO: 'order',
        INDEX: 'index',
        OPEN_INTEREST: 'open_interest',
        FUNDING: 'funding',
        CANDLES: 'kline',
        LIQUIDATIONS: 'liquidation',
        TICKER: 'tickers'
    }
    websocket_endpoints = [
        WebsocketEndpoint('wss://stream.bybit.com/v5/public/linear', instrument_filter=('TYPE', (FUTURES, PERPETUAL)), channel_filter=(websocket_channels[L2_BOOK], websocket_channels[TRADES], websocket_channels[INDEX], websocket_channels[OPEN_INTEREST], websocket_channels[FUNDING], websocket_channels[CANDLES], websocket_channels[LIQUIDATIONS], websocket_channels[TICKER]), sandbox='wss://stream-testnet.bybit.com/v5/public/linear', options={'compression': None}),
        WebsocketEndpoint('wss://stream.bybit.com/v5/public/spot', instrument_filter=('TYPE', (SPOT)), channel_filter=(websocket_channels[L2_BOOK], websocket_channels[TRADES], websocket_channels[CANDLES],), sandbox='wss://stream-testnet.bybit.com/v5/public/spot', options={'compression': None}),
        WebsocketEndpoint('wss://stream.bybit.com/realtime_private', channel_filter=(websocket_channels[ORDER_INFO], websocket_channels[FILLS]), instrument_filter=('QUOTE', ('USDT',)), sandbox='wss://stream-testnet.bybit.com/realtime_private', options={'compression': None}),
    ]
    rest_endpoints = [
        RestEndpoint('https://api.bybit.com', routes=Routes(['/v5/market/instruments-info?&category=linear&status=Trading&limit=1000', '/v5/market/instruments-info?&category=spot&status=Trading&limit=1000']))
    ]
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '1d', '1w', '1M'}
    candle_interval_map = {'1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '2h': '120', '4h': '240', '6h': '360', '1d': 'D', '1w': 'W', '1M': 'M'}

    # Bybit sends delta updates for futures, which might not include some values if they haven't changed.
    # https://bybit-exchange.github.io/docs/v5/websocket/public/ticker
    # Initialize the store to keep snapshots and update the data with deltas
    tickers = {}

    @classmethod
    def timestamp_normalize(cls, ts: Union[int, dt]) -> float:
        if isinstance(ts, int):
            return ts / 1000.0
        else:
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

                    if 'contractType' not in symbol:
                        stype = SPOT
                    elif 'contractType' in symbol:
                        if symbol['contractType'] == 'LinearPerpetual':
                            stype = PERPETUAL
                        elif symbol['contractType'] == 'LinearFutures':
                            stype = FUTURES

                    base = symbol['baseCoin']
                    quote = symbol['quoteCoin']

                    expiry = None

                    if stype is FUTURES:
                        if not symbol['symbol'].endswith(quote):
                            # linear futures
                            if '-' in symbol['symbol']:
                                expiry = symbol['symbol'].split('-')[-1]

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

        self.tickers = {}

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
                       entry['start'],
                       entry['end'],
                       self.candle_interval,
                       entry['confirm'],
                       Decimal(entry['open']),
                       Decimal(entry['close']),
                       Decimal(entry['high']),
                       Decimal(entry['low']),
                       Decimal(entry['volume']),
                       None,
                       ts,
                       raw=entry)
            await self.callback(CANDLES, c, timestamp)

    async def _liquidation(self, msg: dict, timestamp: float):
        '''
        {
            "topic": "liquidation.BTCUSDT",
            "type": "snapshot",
            "ts": 1703485237953,
            "data": {
                "updatedTime": 1703485237953,
                "symbol": "BTCUSDT",
                "side": "Sell",
                "size": "0.003",
                "price": "43511.70"
            }
        }
        '''
        liq = Liquidation(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['data']['symbol']),
            BUY if msg['data']['side'] == 'Buy' else SELL,
            Decimal(msg['data']['size']),
            Decimal(msg['data']['price']),
            None,
            None,
            msg['ts'],
            raw=msg
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
                if 'request' in msg:
                    if msg['request']['op'] == 'auth':
                        LOG.debug("%s: Authenticated successful", conn.uuid)
                elif msg['op'] == 'subscribe':
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
        elif msg['topic'].startswith('liquidation'):
            await self._liquidation(msg, timestamp)
        elif msg['topic'].startswith('tickers'):
            await self._ticker_open_interest_funding_index(msg, timestamp, conn)
        elif "order" in msg["topic"]:
            await self._order(msg, timestamp)
        elif "execution" in msg["topic"]:
            await self._execution(msg, timestamp)
        # elif "position" in msg["topic"]:
        #     await self._balances(msg, timestamp)
        else:
            LOG.warning("%s: Unhandled message type %s", conn.uuid, msg)

    async def subscribe(self, connection: AsyncConnection):
        self.__reset(connection)

        # Bybit does not offer separate channels for open interest, funding, and index price.
        # Instead, it integrates this data into the 'tickers' channel. This approach de-duplicates pairs and
        # subscribes them all at once to the 'tickers' channel.
        tickers_pairs = []
        for chan, pairs in connection.subscription.items():
            if chan in [self.websocket_channels[TICKER], OPEN_INTEREST, FUNDING, INDEX]:
                tickers_pairs += pairs
        tickers_pairs = list(set(tickers_pairs))
        sub = [f"tickers.{pair}" for pair in tickers_pairs]
        if sub:
            await connection.write(json.dumps({"op": "subscribe", "args": sub}))

        for chan in connection.subscription:
            if not self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                for pair in connection.subscription[chan]:
                    sym = str_to_symbol(self.exchange_symbol_to_std_symbol(pair))
                    if sym.type == SPOT:
                        pair = pair.replace('/', '')

                    if self.exchange_channel_to_std(chan) == CANDLES:
                        sub = [f"{self.websocket_channels[CANDLES]}.{self.candle_interval_map[self.candle_interval]}.{pair}"]
                    elif self.exchange_channel_to_std(chan) == L2_BOOK:
                        l2_book_channel = {
                            SPOT: "orderbook.200",
                            FUTURES: "orderbook.200",
                            PERPETUAL: "orderbook.200",
                        }
                        sub = [f"{l2_book_channel[sym.type]}.{pair}"]
                    else:
                        sub = [f"{chan}.{pair}"]

                    if self.exchange_channel_to_std(chan) not in [self.websocket_channels[TICKER], OPEN_INTEREST, FUNDING, INDEX]:
                        await connection.write(json.dumps({"op": "subscribe", "args": sub}))
            else:
                await connection.write(json.dumps(
                    {
                        "op": "subscribe",
                        "args": [f"{chan}"]
                    }
                ))

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

        for key, update in data.items():
            side = BID if key == 'b' else ASK
            if key == 'a' or key == 'b':
                for price, size in update:

                    price = Decimal(price)
                    size = Decimal(size)

                    if size == 0:
                        if price in self._l2_book[pair].book[side]:
                            del self._l2_book[pair].book[side][price]
                    else:
                        self._l2_book[pair].book[side][price] = size

        if update_type == 'delta':
            delta = {BID: data['b'], ASK: data['a']}

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=int(msg['ts']), raw=msg, delta=delta)

    async def _ticker_open_interest_funding_index(self, msg: dict, timestamp: float, conn: AsyncConnection):
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
        symbol = self.exchange_symbol_to_std_symbol(_pair)

        if update_type == 'snapshot':
            self.tickers[symbol] = update

        if update_type == 'delta':
            self.tickers[symbol].update(update)
            update = self.tickers[symbol]

        if 'tickers' in conn.subscription and _pair in conn.subscription['tickers']:
            t = Ticker(
                self.id,
                symbol,
                Decimal(update['bid1Price']) if 'bid1Price' in update else Decimal(0),
                Decimal(update['ask1Price']) if 'ask1Price' in update else Decimal(0),
                int(msg['ts']),
                raw=update
            )
            await self.callback(TICKER, t, timestamp)

        if 'funding' in conn.subscription and _pair in conn.subscription['funding']:
            f = Funding(
                self.id,
                symbol,
                Decimal(update['markPrice']),
                Decimal(update['fundingRate']),
                int(update['nextFundingTime']),
                int(msg['ts']),
                None,
                raw=update
            )
            await self.callback(FUNDING, f, timestamp)

        if 'open_interest' in conn.subscription and _pair in conn.subscription['open_interest']:
            o = OpenInterest(
                self.id,
                symbol,
                Decimal(update['openInterest']),
                int(msg['ts']),
                raw=update
            )

            await self.callback(OPEN_INTEREST, o, timestamp)

        if 'index' in conn.subscription and _pair in conn.subscription['index']:
            i = Index(
                self.id,
                symbol,
                Decimal(update['indexPrice']),
                int(msg['ts']),
                raw=update
            )

            await self.callback(INDEX, i, timestamp)

    async def _order(self, msg: dict, timestamp: float):
        """
        {
            "topic": "order",
            "action": "",
            "data": [
                {
                    "order_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                    "order_link_id": "",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "order_type": "Limit",
                    "price": 11000,
                    "qty": 0.001,
                    "leaves_qty": 0.001,
                    "last_exec_price": 0,
                    "cum_exec_qty": 0,
                    "cum_exec_value": 0,
                    "cum_exec_fee": 0,
                    "time_in_force": "GoodTillCancel",
                    "create_type": "CreateByUser",
                    "cancel_type": "UNKNOWN",
                    "order_status": "New",
                    "take_profit": 0,
                    "stop_loss": 0,
                    "trailing_stop": 0,
                    "reduce_only": false,
                    "close_on_trigger": false,
                    "create_time": "2020-08-12T21:18:40.780039678Z",
                    "update_time": "2020-08-12T21:18:40.787986415Z"
                }
            ]
        }
        """
        order_status = {
            'Created': SUBMITTING,
            'Rejected': FAILED,
            'New': OPEN,
            'PartiallyFilled': PARTIAL,
            'Filled': FILLED,
            'Cancelled': CANCELLED,
            'PendingCancel': CANCELLING
        }

        for i in range(len(msg['data'])):
            data = msg['data'][i]

            oi = OrderInfo(
                self.id,
                self.exchange_symbol_to_std_symbol(data['symbol']),
                data["order_id"],
                BUY if data["side"] == 'Buy' else SELL,
                order_status[data["order_status"]],
                LIMIT if data['order_type'] == 'Limit' else MARKET,
                Decimal(data['price']),
                Decimal(data['qty']),
                Decimal(data['qty']) - Decimal(data['cum_exec_qty']),
                self.timestamp_normalize(data.get('update_time') or data.get('O') or data.get('timestamp')),
                raw=data,
            )
            await self.callback(ORDER_INFO, oi, timestamp)

    async def _execution(self, msg: dict, timestamp: float):
        '''
        {
            "topic": "execution",
            "data": [
                {
                    "symbol": "BTCUSD",
                    "side": "Buy",
                    "order_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                    "exec_id": "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6",
                    "order_link_id": "",
                    "price": "8300",
                    "order_qty": 1,
                    "exec_type": "Trade",
                    "exec_qty": 1,
                    "exec_fee": "0.00000009",
                    "leaves_qty": 0,
                    "is_maker": false,
                    "trade_time": "2020-01-14T14:07:23.629Z" // trade time
                }
            ]
        }
        '''
        for entry in msg['data']:
            symbol = self.exchange_symbol_to_std_symbol(entry['symbol'])
            f = Fill(
                self.id,
                symbol,
                BUY if entry['side'] == 'Buy' else SELL,
                Decimal(entry['exec_qty']),
                Decimal(entry['price']),
                Decimal(entry['exec_fee']),
                entry['exec_id'],
                entry['order_id'],
                None,
                MAKER if entry['is_maker'] else TAKER,
                entry['trade_time'].timestamp(),
                raw=entry
            )
            await self.callback(FILLS, f, timestamp)

    # async def _balances(self, msg: dict, timestamp: float):
    #    for i in range(len(msg['data'])):
    #        data = msg['data'][i]
    #        symbol = self.exchange_symbol_to_std_symbol(data['symbol'])
    #        await self.callback(BALANCES, feed=self.id, symbol=symbol, data=data, receipt_timestamp=timestamp)

    async def authenticate(self, conn: AsyncConnection):
        if any(self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in conn.subscription):
            auth = self._auth(self.key_id, self.key_secret)
            LOG.debug(f"{conn.uuid}: Sending authentication request with message {auth}")
            await conn.write(auth)

    def _auth(self, key_id: str, key_secret: str) -> str:
        # https://bybit-exchange.github.io/docs/inverse/#t-websocketauthentication

        expires = int((time.time() + 60)) * 1000
        signature = str(hmac.new(bytes(key_secret, 'utf-8'), bytes(f'GET/realtime{expires}', 'utf-8'), digestmod='sha256').hexdigest())
        return json.dumps({'op': 'auth', 'args': [key_id, expires, signature]})
