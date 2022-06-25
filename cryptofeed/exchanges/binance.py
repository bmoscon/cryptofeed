'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from asyncio import create_task, sleep
from collections import defaultdict
from decimal import Decimal
import requests
import time
from typing import Dict, Union, Tuple
from urllib.parse import urlencode

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll, HTTPConcurrentPoll, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BALANCES, BID, BINANCE, BUY, CANDLES, FUNDING, FUTURES, L2_BOOK, LIMIT, LIQUIDATIONS, MARKET, OPEN_INTEREST, ORDER_INFO, PERPETUAL, SELL, SPOT, TICKER, TRADES, FILLED, UNFILLED
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.binance_rest import BinanceRestMixin
from cryptofeed.types import Trade, Ticker, Candle, Liquidation, Funding, OrderBook, OrderInfo, Balance

REFRESH_SNAPSHOT_MIN_INTERVAL_SECONDS = 60

LOG = logging.getLogger('feedhandler')


class Binance(Feed, BinanceRestMixin):
    id = BINANCE
    websocket_endpoints = [WebsocketEndpoint('wss://stream.binance.com:9443', sandbox='wss://testnet.binance.vision')]
    rest_endpoints = [RestEndpoint('https://api.binance.com', routes=Routes('/api/v3/exchangeInfo', l2book='/api/v3/depth?symbol={}&limit={}', authentication='/api/v3/userDataStream'), sandbox='https://testnet.binance.vision')]

    valid_depths = [5, 10, 20, 50, 100, 500, 1000, 5000]
    # m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'}
    valid_depth_intervals = {'100ms', '1000ms'}
    websocket_channels = {
        L2_BOOK: 'depth',
        TRADES: 'aggTrade',
        TICKER: 'bookTicker',
        CANDLES: 'kline_',
        BALANCES: BALANCES,
        ORDER_INFO: ORDER_INFO
    }
    request_limit = 20

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        for symbol in data['symbols']:
            if symbol.get('status', 'TRADING') != "TRADING":
                continue
            if symbol.get('contractStatus', 'TRADING') != "TRADING":
                continue

            expiration = None
            stype = SPOT
            if symbol.get('contractType') == 'PERPETUAL':
                stype = PERPETUAL
            elif symbol.get('contractType') in ('CURRENT_QUARTER', 'NEXT_QUARTER'):
                stype = FUTURES
                expiration = symbol['symbol'].split("_")[1]

            s = Symbol(symbol['baseAsset'], symbol['quoteAsset'], type=stype, expiry_date=expiration)
            ret[s.normalized] = symbol['symbol']
            info['tick_size'][s.normalized] = symbol['filters'][0]['tickSize']
            info['instrument_type'][s.normalized] = stype
        return ret, info

    def __init__(self, depth_interval='100ms', **kwargs):
        """
        depth_interval: str
            time between l2_book/delta updates {'100ms', '1000ms'} (different from BINANCE_FUTURES & BINANCE_DELIVERY)
        """
        if depth_interval is not None and depth_interval not in self.valid_depth_intervals:
            raise ValueError(f"Depth interval must be one of {self.valid_depth_intervals}")

        super().__init__(**kwargs)
        self.depth_interval = depth_interval
        self._open_interest_cache = {}
        self._reset()

    def _address(self) -> Union[str, Dict]:
        """
        Binance has a 200 pair/stream limit per connection, so we need to break the address
        down into multiple connections if necessary. Because the key is currently not used
        for the address dict, we can just set it to the last used stream, since this will be
        unique.

        The generic connect method supplied by Feed will take care of creating the
        correct connection objects from the addresses.
        """
        if self.requires_authentication:
            listen_key = self._generate_token()
            address = self.address
            address += '/ws/' + listen_key
        else:
            address = self.address
            address += '/stream?streams='
        subs = []

        is_any_private = any(self.is_authenticated_channel(chan) for chan in self.subscription)
        is_any_public = any(not self.is_authenticated_channel(chan) for chan in self.subscription)
        if is_any_private and is_any_public:
            raise ValueError("Private channels should be subscribed in separate feeds vs public channels")
        if all(self.is_authenticated_channel(chan) for chan in self.subscription):
            return address

        for chan in self.subscription:
            normalized_chan = self.exchange_channel_to_std(chan)
            if normalized_chan == OPEN_INTEREST:
                continue
            if self.is_authenticated_channel(normalized_chan):
                continue

            stream = chan
            if normalized_chan == CANDLES:
                stream = f"{chan}{self.candle_interval}"
            elif normalized_chan == L2_BOOK:
                stream = f"{chan}@{self.depth_interval}"

            for pair in self.subscription[chan]:
                # for everything but premium index the symbols need to be lowercase.
                if pair.startswith("p"):
                    if normalized_chan != CANDLES:
                        raise ValueError("Premium Index Symbols only allowed on Candle data feed")
                else:
                    pair = pair.lower()
                subs.append(f"{pair}@{stream}")

        if 0 < len(subs) < 200:
            return address + '/'.join(subs)
        else:
            def split_list(_list: list, n: int):
                for i in range(0, len(_list), n):
                    yield _list[i:i + n]

            return [address + '/'.join(chunk) for chunk in split_list(subs, 200)]

    def _reset(self):
        self._l2_book = {}
        self.last_update_id = {}

    async def _refresh_token(self):
        while True:
            await sleep(30 * 60)
            if self._auth_token is None:
                raise ValueError('There is no token to refresh')
            payload = {'listenKey': self._auth_token}
            r = requests.put(f'{self.rest_endpoints[0].route("authentication", sandbox=self.sandbox)}?{urlencode(payload)}', headers={'X-MBX-APIKEY': self.key_id})
            r.raise_for_status()

    def _generate_token(self) -> str:
        url = self.rest_endpoints[0].route('authentication', sandbox=self.sandbox)
        r = requests.post(url, headers={'X-MBX-APIKEY': self.key_id})
        r.raise_for_status()
        response = r.json()
        if 'listenKey' in response:
            self._auth_token = response['listenKey']
            return self._auth_token
        else:
            raise ValueError(f'Unable to retrieve listenKey token from {url}')

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            "e": "aggTrade",  // Event type
            "E": 123456789,   // Event time
            "s": "BNBBTC",    // Symbol
            "a": 12345,       // Aggregate trade ID
            "p": "0.001",     // Price
            "q": "100",       // Quantity
            "f": 100,         // First trade ID
            "l": 105,         // Last trade ID
            "T": 123456785,   // Trade time
            "m": true,        // Is the buyer the market maker?
            "M": true         // Ignore
        }
        """
        t = Trade(self.id,
                  self.exchange_symbol_to_std_symbol(msg['s']),
                  SELL if msg['m'] else BUY,
                  Decimal(msg['q']),
                  Decimal(msg['p']),
                  self.timestamp_normalize(msg['T']),
                  id=str(msg['a']),
                  raw=msg)
        await self.callback(TRADES, t, timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            'u': 382569232,
            's': 'FETUSDT',
            'b': '0.36031000',
            'B': '1500.00000000',
            'a': '0.36092000',
            'A': '176.40000000'
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['s'])
        bid = Decimal(msg['b'])
        ask = Decimal(msg['a'])

        # Binance does not have a timestamp in this update, but the two futures APIs do
        if 'E' in msg:
            ts = self.timestamp_normalize(msg['E'])
        else:
            ts = timestamp

        t = Ticker(self.id, pair, bid, ask, ts, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _liquidations(self, msg: dict, timestamp: float):
        """
        {
        "e":"forceOrder",       // Event Type
        "E":1568014460893,      // Event Time
        "o":{
            "s":"BTCUSDT",      // Symbol
            "S":"SELL",         // Side
            "o":"LIMIT",        // Order Type
            "f":"IOC",          // Time in Force
            "q":"0.014",        // Original Quantity
            "p":"9910",         // Price
            "ap":"9910",        // Average Price
            "X":"FILLED",       // Order Status
            "l":"0.014",        // Order Last Filled Quantity
            "z":"0.014",        // Order Filled Accumulated Quantity
            "T":1568014460893,  // Order Trade Time
            }
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['o']['s'])
        liq = Liquidation(self.id,
                          pair,
                          SELL if msg['o']['S'] == 'SELL' else BUY,
                          Decimal(msg['o']['q']),
                          Decimal(msg['o']['p']),
                          None,
                          FILLED if msg['o']['X'] == 'FILLED' else UNFILLED,
                          self.timestamp_normalize(msg['E']),
                          raw=msg)
        await self.callback(LIQUIDATIONS, liq, receipt_timestamp=timestamp)

    def _check_update_id(self, std_pair: str, msg: dict) -> bool:
        """
        Messages will be queued while fetching snapshot and we can return a book_callback
        using this msg's data instead of waiting for the next update.
        """
        if self._l2_book[std_pair].delta is None and msg['u'] <= self.last_update_id[std_pair]:
            return True
        elif msg['U'] <= self.last_update_id[std_pair] and msg['u'] <= self.last_update_id[std_pair]:
            # Old message, can ignore it
            return True
        elif msg['U'] <= self.last_update_id[std_pair] + 1 <= msg['u']:
            self.last_update_id[std_pair] = msg['u']
            return False
        elif self.last_update_id[std_pair] + 1 == msg['U']:
            self.last_update_id[std_pair] = msg['u']
            return False
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            return True

    async def _snapshot(self, pair: str) -> None:
        max_depth = self.max_depth if self.max_depth else 1000
        if max_depth not in self.valid_depths:
            for d in self.valid_depths:
                if d > max_depth:
                    max_depth = d
                    break

        resp = await self.http_conn.read(self.rest_endpoints[0].route('l2book', self.sandbox).format(pair, max_depth))
        resp = json.loads(resp, parse_float=Decimal)
        timestamp = self.timestamp_normalize(resp['E']) if 'E' in resp else None

        std_pair = self.exchange_symbol_to_std_symbol(pair)
        self.last_update_id[std_pair] = resp['lastUpdateId']
        self._l2_book[std_pair] = OrderBook(self.id, std_pair, max_depth=self.max_depth, bids={Decimal(u[0]): Decimal(u[1]) for u in resp['bids']}, asks={Decimal(u[0]): Decimal(u[1]) for u in resp['asks']})
        await self.book_callback(L2_BOOK, self._l2_book[std_pair], time.time(), timestamp=timestamp, raw=resp, sequence_number=self.last_update_id[std_pair])

    async def _book(self, msg: dict, pair: str, timestamp: float):
        """
        {
            "e": "depthUpdate", // Event type
            "E": 123456789,     // Event time
            "s": "BNBBTC",      // Symbol
            "U": 157,           // First update ID in event
            "u": 160,           // Final update ID in event
            "b": [              // Bids to be updated
                    [
                        "0.0024",       // Price level to be updated
                        "10"            // Quantity
                    ]
            ],
            "a": [              // Asks to be updated
                    [
                        "0.0026",       // Price level to be updated
                        "100"           // Quantity
                    ]
            ]
        }
        """
        exchange_pair = pair
        pair = self.exchange_symbol_to_std_symbol(pair)

        if pair not in self._l2_book:
            await self._snapshot(exchange_pair)

        skip_update = self._check_update_id(pair, msg)
        if skip_update:
            return

        delta = {BID: [], ASK: []}

        for s, side in (('b', BID), ('a', ASK)):
            for update in msg[s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])
                delta[side].append((price, amount))

                if amount == 0:
                    if price in self._l2_book[pair].book[side]:
                        del self._l2_book[pair].book[side][price]
                else:
                    self._l2_book[pair].book[side][price] = amount

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(msg['E']), raw=msg, delta=delta, sequence_number=self.last_update_id[pair])

    async def _funding(self, msg: dict, timestamp: float):
        """
        {
            "e": "markPriceUpdate",  // Event type
            "E": 1562305380000,      // Event time
            "s": "BTCUSDT",          // Symbol
            "p": "11185.87786614",   // Mark price
            "r": "0.00030000",       // Funding rate
            "T": 1562306400000       // Next funding time
        }

        BinanceFutures
        {
            "e": "markPriceUpdate",     // Event type
            "E": 1562305380000,         // Event time
            "s": "BTCUSDT",             // Symbol
            "p": "11185.87786614",      // Mark price
            "i": "11784.62659091"       // Index price
            "P": "11784.25641265",      // Estimated Settle Price, only useful in the last hour before the settlement starts
            "r": "0.00030000",          // Funding rate
            "T": 1562306400000          // Next funding time
        }
        """
        next_time = self.timestamp_normalize(msg['T']) if msg['T'] > 0 else None
        rate = Decimal(msg['r']) if msg['r'] else None
        if next_time is None:
            rate = None

        f = Funding(self.id,
                    self.exchange_symbol_to_std_symbol(msg['s']),
                    Decimal(msg['p']),
                    rate,
                    next_time,
                    self.timestamp_normalize(msg['E']),
                    predicted_rate=Decimal(msg['P']) if 'P' in msg and msg['P'] is not None else None,
                    raw=msg)
        await self.callback(FUNDING, f, timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        """
        {
            'e': 'kline',
            'E': 1615927655524,
            's': 'BTCUSDT',
            'k': {
                't': 1615927620000,
                'T': 1615927679999,
                's': 'BTCUSDT',
                'i': '1m',
                'f': 710917276,
                'L': 710917780,
                'o': '56215.99000000',
                'c': '56232.07000000',
                'h': '56238.59000000',
                'l': '56181.99000000',
                'v': '13.80522200',
                'n': 505,
                'x': False,
                'q': '775978.37383076',
                'V': '7.19660600',
                'Q': '404521.60814919',
                'B': '0'
            }
        }
        """
        if self.candle_closed_only and not msg['k']['x']:
            return
        c = Candle(self.id,
                   self.exchange_symbol_to_std_symbol(msg['s']),
                   msg['k']['t'] / 1000,
                   msg['k']['T'] / 1000,
                   msg['k']['i'],
                   msg['k']['n'],
                   Decimal(msg['k']['o']),
                   Decimal(msg['k']['c']),
                   Decimal(msg['k']['h']),
                   Decimal(msg['k']['l']),
                   Decimal(msg['k']['v']),
                   msg['k']['x'],
                   self.timestamp_normalize(msg['E']),
                   raw=msg)
        await self.callback(CANDLES, c, timestamp)

    async def _account_update(self, msg: dict, timestamp: float):
        """
        {
            "e": "outboundAccountPosition", //Event type
            "E": 1564034571105,             //Event Time
            "u": 1564034571073,             //Time of last account update
            "B": [                          //Balances Array
                {
                "a": "ETH",                 //Asset
                "f": "10000.000000",        //Free
                "l": "0.000000"             //Locked
                }
            ]
        }
        """
        for balance in msg['B']:
            b = Balance(
                self.id,
                balance['a'],
                Decimal(balance['f']),
                Decimal(balance['l']),
                raw=msg)
            await self.callback(BALANCES, b, timestamp)

    async def _order_update(self, msg: dict, timestamp: float):
        """
        {
            "e": "executionReport",        // Event type
            "E": 1499405658658,            // Event time
            "s": "ETHBTC",                 // Symbol
            "c": "mUvoqJxFIILMdfAW5iGSOW", // Client order ID
            "S": "BUY",                    // Side
            "o": "LIMIT",                  // Order type
            "f": "GTC",                    // Time in force
            "q": "1.00000000",             // Order quantity
            "p": "0.10264410",             // Order price
            "P": "0.00000000",             // Stop price
            "F": "0.00000000",             // Iceberg quantity
            "g": -1,                       // OrderListId
            "C": "",                       // Original client order ID; This is the ID of the order being canceled
            "x": "NEW",                    // Current execution type
            "X": "NEW",                    // Current order status
            "r": "NONE",                   // Order reject reason; will be an error code.
            "i": 4293153,                  // Order ID
            "l": "0.00000000",             // Last executed quantity
            "z": "0.00000000",             // Cumulative filled quantity
            "L": "0.00000000",             // Last executed price
            "n": "0",                      // Commission amount
            "N": null,                     // Commission asset
            "T": 1499405658657,            // Transaction time
            "t": -1,                       // Trade ID
            "I": 8641984,                  // Ignore
            "w": true,                     // Is the order on the book?
            "m": false,                    // Is this trade the maker side?
            "M": false,                    // Ignore
            "O": 1499405658657,            // Order creation time
            "Z": "0.00000000",             // Cumulative quote asset transacted quantity
            "Y": "0.00000000",             // Last quote asset transacted quantity (i.e. lastPrice * lastQty)
            "Q": "0.00000000"              // Quote Order Qty
        }
        """
        oi = OrderInfo(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['s']),
            str(msg['i']),
            BUY if msg['S'].lower() == 'buy' else SELL,
            msg['x'],
            LIMIT if msg['o'].lower() == 'limit' else MARKET if msg['o'].lower() == 'market' else None,
            Decimal(msg['Z']) / Decimal(msg['z']) if not Decimal.is_zero(Decimal(msg['z'])) else None,
            Decimal(msg['q']),
            Decimal(msg['q']) - Decimal(msg['z']),
            self.timestamp_normalize(msg['E']),
            raw=msg
        )
        await self.callback(ORDER_INFO, oi, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Handle account updates from User Data Stream
        if self.requires_authentication:
            msg_type = msg['e']
            if msg_type == 'outboundAccountPosition':
                await self._account_update(msg, timestamp)
            elif msg_type == 'executionReport':
                await self._order_update(msg, timestamp)
            return
        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']
        pair = pair.upper()
        if 'e' in msg:
            if msg['e'] == 'depthUpdate':
                await self._book(msg, pair, timestamp)
            elif msg['e'] == 'aggTrade':
                await self._trade(msg, timestamp)
            elif msg['e'] == 'forceOrder':
                await self._liquidations(msg, timestamp)
            elif msg['e'] == 'markPriceUpdate':
                await self._funding(msg, timestamp)
            elif msg['e'] == 'kline':
                await self._candle(msg, timestamp)
            else:
                LOG.warning("%s: Unexpected message received: %s", self.id, msg)
        elif 'A' in msg:
            await self._ticker(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        # Binance does not have a separate subscribe message, the
        # subscription information is included in the
        # connection endpoint
        if isinstance(conn, (HTTPPoll, HTTPConcurrentPoll)):
            self._open_interest_cache = {}
        else:
            self._reset()
        if self.requires_authentication:
            create_task(self._refresh_token())
