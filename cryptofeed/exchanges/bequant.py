'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hashlib
import hmac
import random
import string
from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, Tuple, Callable, List

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BALANCES, BID, ASK, BUY, BEQUANT, EXPIRED, L2_BOOK, LIMIT, ORDER_INFO, SELL, STOP_LIMIT, STOP_MARKET, TICKER, TRADES, CANDLES, OPEN, PARTIAL, CANCELLED, SUSPENDED, FILLED, TRANSACTIONS, MARKET, MAKER_OR_CANCEL
from cryptofeed.feed import Feed
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.symbols import Symbol
from cryptofeed.types import Trade, Ticker, Candle


LOG = logging.getLogger('feedhandler')


class Bequant(Feed):
    id = BEQUANT
    symbol_endpoint = 'https://api.bequant.io/api/2/public/symbol'
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'}
    websocket_channels = {
        BALANCES: 'subscribeBalance',
        TRANSACTIONS: 'subscribeTransactions',
        ORDER_INFO: 'subscribeReports',
        L2_BOOK: 'subscribeOrderbook',
        TRADES: 'subscribeTrades',
        TICKER: 'subscribeTicker',
        CANDLES: 'subscribeCandles'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        normalized_currencies = {
            'USD': 'USDT',
            'USDB': 'USD',
        }

        for symbol in data:
            # Filter out pairs ending in _BQX
            # From Bequant support: "BQX pairs are our 0 taker fee pairs that are only to be used by our retail broker clients (the BQX is to differentiate them from the traditional pairs)"
            if symbol['id'][-4:] == '_BQX':
                continue

            base_currency = normalized_currencies[symbol['baseCurrency']] if symbol['baseCurrency'] in normalized_currencies else symbol['baseCurrency']
            quote_currency = normalized_currencies[symbol['quoteCurrency']] if symbol['quoteCurrency'] in normalized_currencies else symbol['quoteCurrency']
            s = Symbol(base_currency, quote_currency)
            ret[s.normalized] = symbol['id']
            info['tick_size'][s.normalized] = symbol['tickSize']
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, candle_interval='1m', **kwargs):
        urls = {
            'market': 'wss://api.bequant.io/api/2/ws/public',
            'trading': 'wss://api.bequant.io/api/2/ws/trading',
            'account': 'wss://api.bequant.io/api/2/ws/account',
        }
        super().__init__(urls, **kwargs)
        if candle_interval not in self.valid_candle_intervals:
            raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")
        interval_map = {'1m': 'M1', '3m': 'M3', '5m': 'M5', '15m': 'M15', '30m': 'M30', '1h': 'H1', '4h': 'H4', '1d': 'D1', '1w': 'D7', '1M': '1M'}
        self.candle_interval = interval_map[candle_interval]
        self.normalize_interval = {value: key for key, value in interval_map.items()}
        self.__reset()

    def __reset(self):
        self._l2_book = {}
        self.seq_no = {}

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            "ask": "0.054464", <- best ask
            "bid": "0.054463", <- best bid
            "last": "0.054463", <- last trade
            "open": "0.057133", <- last trade price 24hrs previous
            "low": "0.053615", <- lowest trade in past 24hrs
            "high": "0.057559", <- highest trade in past 24hrs
            "volume": "33068.346", <- total base currency traded in past 24hrs
            "volumeQuote": "1832.687530809", <- total quote currency traded in past 24hrs
            "timestamp": "2017-10-19T15:45:44.941Z", <- last update or refresh ticker timestamp
            "symbol": "ETHBTC"
        }
        """
        t = Ticker(self.id, self.exchange_symbol_to_std_symbol(msg['symbol']), Decimal(msg['bid']), Decimal(msg['ask']), self.timestamp_normalize(msg['timestamp']), raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _book_snapshot(self, msg: dict, ts: float):
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        self._l2_book[pair] = {
            BID: sd({
                Decimal(bid['price']): Decimal(bid['size']) for bid in msg['bid']
            }),
            ASK: sd({
                Decimal(ask['price']): Decimal(ask['size']) for ask in msg['ask']
            })
        }
        await self.book_callback(self._l2_book[pair], L2_BOOK, pair, True, None, self.timestamp_normalize(msg['timestamp']), ts)

    async def _book_update(self, msg: dict, ts: float):
        delta = {BID: [], ASK: []}
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        for side in ('bid', 'ask'):
            s = BID if side == 'bid' else ASK
            for entry in msg[side]:
                price = Decimal(entry['price'])
                amount = Decimal(entry['size'])
                if amount == 0:
                    delta[s].append((price, 0))
                    del self._l2_book[pair][s][price]
                else:
                    delta[s].append((price, amount))
                    self._l2_book[pair][s][price] = amount
        await self.book_callback(self._l2_book[pair], L2_BOOK, pair, False, delta, self.timestamp_normalize(msg['timestamp']), ts)

    async def _trades(self, msg: dict, timestamp: float):
        """
        "params": {
            "data": [
            {
                "id": 54469813,
                "price": "0.054670",
                "quantity": "0.183",
                "side": "buy",
                "timestamp": "2017-10-19T16:34:25.041Z"
            }
            ],
            "symbol": "ETHBTC"
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        for update in msg['data']:
            t = Trade(self.id,
                      pair,
                      BUY if update['side'] == 'buy' else SELL,
                      Decimal(update['quantity']),
                      Decimal(update['price']),
                      self.timestamp_normalize(update['timestamp']),
                      id=str(update['id']),
                      raw=update)
            await self.callback(TRADES, t, timestamp)

    async def _candles(self, msg: dict, timestamp: float):
        """
        {
            "jsonrpc": "2.0",
            "method": "updateCandles",
            "params": {
                "data": [
                    {
                        "timestamp": "2017-10-19T16:30:00.000Z",
                        "open": "0.054614",
                        "close": "0.054465",
                        "min": "0.054339",
                        "max": "0.054724",
                        "volume": "141.268",
                        "volumeQuote": "7.709353873"
                    }
                ],
                "symbol": "ETHBTC",
                "period": "M30"
            }
        }
        """

        interval = str(self.normalize_interval[msg['period']])

        for candle in msg['data']:
            start = self.timestamp_normalize(candle['timestamp'])
            end = start + timedelta_str_to_sec(interval) - 1
            c = Candle(
                self.id,
                self.exchange_symbol_to_std_symbol(msg['symbol']),
                start,
                end,
                interval,
                None,
                Decimal(candle['open']),
                Decimal(candle['close']),
                Decimal(candle['max']),
                Decimal(candle['min']),
                Decimal(candle['volume']),
                None,
                None,
                raw=candle
            )
            await self.callback(CANDLES, c, timestamp)

    async def _order_status(self, msg: str, conn: AsyncConnection, ts: float):
        status_lookup = {
            'new': OPEN,
            'partiallyFilled': PARTIAL,
            'filled': FILLED,
            'canceled': CANCELLED,
            'expired': EXPIRED,
            'suspended': SUSPENDED,
        }
        type_lookup = {
            'limit': LIMIT,
            'market': MARKET,
            'stopLimit': STOP_LIMIT,
            'stopMarket': STOP_MARKET,
        }

        """
        Example response:
        {
            "jsonrpc": "2.0",
            "method": "report",
            "params": {
                "id": "4345697765",
                "clientOrderId": "53b7cf917963464a811a4af426102c19",
                "symbol": "ETHBTC",
                "side": "sell",
                "status": "filled",
                "type": "limit",
                "timeInForce": "GTC",
                "quantity": "0.001",
                "price": "0.053868",
                "cumQuantity": "0.001",
                "postOnly": false,
                "createdAt": "2017-10-20T12:20:05.952Z",
                "updatedAt": "2017-10-20T12:20:38.708Z",
                "reportType": "trade",
                "tradeQuantity": "0.001",
                "tradePrice": "0.053868",
                "tradeId": 55051694,
                "tradeFee": "-0.000000005"
            }
        }
        """
        res = {
            'symbol': msg["symbol"],
            # 'symbol': self.exchange_symbol_to_std_symbol(msg["symbol"]),
            'status': status_lookup[msg["status"]],
            'order_id': msg["id"],
            'side': SELL if msg["side"] == 'sell' else BUY,
            'order_type': type_lookup[msg["type"]],
            'timestamp': self.timestamp_normalize(msg["updatedAt"]) if msg["updatedAt"] else self.timestamp_normalize(msg["createdAt"]),
            'receipt_timestamp': ts,
            'report_type': msg['reportType'],
            'client_order_id': msg["clientOrderId"],
            'order_policy': msg["timeInForce"],
            'order_quantity': Decimal(msg["quantity"]),
            'price': Decimal(msg["price"]),
            'cumulative_quant': Decimal(msg["cumQuantity"]),
            MAKER_OR_CANCEL: bool(msg["postOnly"]),
        }

        if msg["reportType"] == 'trade':
            res['trade_quantity'] = Decimal(msg["tradeQuantity"])
            res['trade_price'] = Decimal(msg["tradePrice"])
            res['trade_id'] = msg['tradeID']
            res['trade_fee'] = Decimal(msg['tradeFee'])

        # Conn passed up to callback as way of handing authenticated ws (with trading endpoint) to application
        # Temporary solution until ws trading implemented
        await self.callback(ORDER_INFO, feed=self.id, conn=conn, **res)

    async def _transactions(self, msg: str, conn: AsyncConnection, ts: float):

        """A transaction notification occurs each time the transaction has been changed, such as creating a transaction,
        updating the pending state (for example the hash assigned) or completing a transaction.
        This is the easiest way to track deposits or develop real-time asset monitoring."""

        keys = ['id', 'index', 'currency', 'amount', 'fee', 'address', 'paymentId', 'hash', 'status', 'type', 'subType', 'senders', 'offchainId', 'confirmations', 'publicComment', 'errorCode', 'createdAt', 'updatedAt']

        decimalize = ['amount', 'fee']
        ts_normalize = ['createdAt', 'updatedAt']
        transaction = {k: Decimal(msg[k]) if k in decimalize else self.timestamp_normalize(msg[k]) if k in ts_normalize else k for k in keys if k in msg}

        transaction['receipt_timestamp'] = ts
        # transaction = {
        #     'receipt_timestamp': ts,
        #     'tx_id': msg['id'],
        #     'exch_index': msg['index'],
        #     'currency': msg['currency'],
        #     'amount': Decimal(msg['amount']),
        #     'fee': Decimal(msg['fee']),
        #     'address': msg['address'],
        #     'payment_id': msg['paymentId'],
        #     'tx_hash': msg['hash'],
        #     'status': msg['status'],
        #     'tx_type': msg['type'],
        #     'tx_subType': msg['subType'],
        #     'senders': msg['senders'],
        #     'off_chain_id': msg['offchainId'],
        #     'confirmations': msg['confirmations'],
        # }

        await self.callback(TRANSACTIONS, feed=self.id, conn=conn, **transaction)

    async def _balances(self, msg: str, conn: AsyncConnection, ts: float):
        accounts = [{k: Decimal(v) if k in ['available', 'reserved'] else v for (k, v) in account.items()} for account in msg]

        await self.callback(BALANCES, feed=self.id, conn=conn, accounts=accounts)

    async def message_handler(self, msg: str, conn: AsyncConnection, ts: float):

        msg = json.loads(msg, parse_float=Decimal)

        if 'params' in msg and 'sequence' in msg['params']:
            pair = msg['params']['symbol']
            if pair in self.seq_no:
                if self.seq_no[pair] + 1 != msg['params']['sequence']:
                    if self.seq_no[pair] >= msg['params']['sequence']:
                        return
                    LOG.warning("%s: Missing sequence number detected for %s", self.id, pair)
                    raise MissingSequenceNumber("Missing sequence number, restarting")
            self.seq_no[pair] = msg['params']['sequence']

        if 'method' in msg:
            m = msg['method']
            params = msg['params']
            if m == 'ticker':
                await self._ticker(params, ts)
            elif m == 'snapshotOrderbook':
                await self._book_snapshot(params, ts)
            elif m == 'updateOrderbook':
                await self._book_update(params, ts)
            elif m in ('updateTrades', 'snapshotTrades'):
                await self._trades(params, ts)
            elif m in ('snapshotCandles', 'updateCandles'):
                await self._candles(params, ts)
            elif m in ('activeOrders', 'report'):
                if isinstance(params, list):
                    for entry in params:
                        # Conn passed up to callback as way of handing authenticated ws (with trading endpoint) to application
                        # Temporary fix until ws trading implemented
                        await self._order_status(entry, conn, ts)
                else:
                    await self._order_status(params, conn, ts)
            elif m == 'updateTransaction':
                # Ditto for 'account' ws conn. (Same auth, different endpoint)
                await self._transactions(params, conn, ts)
            elif m == 'balance':
                if isinstance(params, list):
                    for entry in params:
                        await self._balances(entry, conn, ts)
                else:
                    await self._balances(params, conn, ts)
            else:
                LOG.warning(f"{self.id}: Invalid message received on {conn.uuid}: {msg}")

        else:
            if 'error' in msg:
                LOG.error(f"{self.id}: Received error on {conn.uuid}: {msg['error']}")

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []

        for chan in self.subscription:
            chan = self.exchange_channel_to_std(chan)
            if self.is_authenticated_channel(chan):
                LOG.info(f'{self.id}: {chan} will be authenticated')
                if chan == ORDER_INFO:
                    ret.append((WSAsyncConn(self.address['trading'], self.id, **self.ws_defaults), self.subscribe, self.message_handler, self.authenticate))
                if chan in [BALANCES, TRANSACTIONS]:
                    ret.append((WSAsyncConn(self.address['account'], self.id, **self.ws_defaults), self.subscribe, self.message_handler, self.authenticate))
            else:
                ret.append((WSAsyncConn(self.address['market'], self.id, **self.ws_defaults), self.subscribe, self.message_handler, self.authenticate))
        return ret

    async def authenticate(self, conn: AsyncConnection):
        if self.requires_authentication:
            # https://api.bequant.io/#socket-session-authentication
            # Nonce should be random string
            nonce = 'h'.join(random.choices(string.ascii_letters + string.digits, k=16)).encode('utf-8')
            signature = hmac.new(self.key_secret.encode('utf-8'), nonce, hashlib.sha256).hexdigest()

            auth = {
                "method": "login",
                "params": {
                    "algo": "HS256",
                    "pKey": self.key_id,
                    "nonce": nonce.decode(),
                    "signature": signature
                },
                "id": conn.uuid
            }

            await conn.write(json.dumps(auth))
            LOG.debug(f"{conn.uuid}: Authenticating with message: {auth}")
            return conn

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        for chan, symbols in self.subscription.items():
            # These channel subs fail if provided with symbol data. "params" must be blank.
            if chan in ['subscribeTransactions', 'subscribeBalance', 'subscribeReports']:
                LOG.debug(f'Subscribing to {chan} with no symbols')
                await conn.write(json.dumps(
                    {
                        "method": chan,
                        "params": {},
                        "id": conn.uuid
                    }
                ))
            else:
                for symbol in symbols:
                    params = {
                        "symbol": symbol,
                    }
                    if chan == "subscribeCandles":
                        params['period'] = self.candle_interval
                    LOG.debug(f'{self.id}: Subscribing to "{chan}"" with params {params}')
                    await conn.write(json.dumps(
                        {
                            "method": chan,
                            "params": params,
                            "id": conn.uuid
                        }
                    ))
