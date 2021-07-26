'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from datetime import datetime as dt
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BALANCES, BID, ASK, BUY, CANCELLED, CANCEL_ORDER, CANDLES, COINBASE, FILLED, FILL_OR_KILL, IMMEDIATE_OR_CANCEL, L2_BOOK, L3_BOOK, LIMIT, MAKER_OR_CANCEL, MARKET, OPEN, ORDER_INFO, ORDER_STATUS, PARTIAL, PENDING, PLACE_ORDER, SELL, TICKER, TRADES, TRADE_HISTORY
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize
from cryptofeed.symbols import Symbol
from cryptofeed.exceptions import UnexpectedMessage


LOG = logging.getLogger('feedhandler')


class Coinbase(Feed):
    id = COINBASE
    api = "https://api.pro.coinbase.com"
    sandbox_api = "https://api-public.sandbox.pro.coinbase.com"
    symbol_endpoint = 'https://api.pro.coinbase.com/products'
    request_limit = 10
    rate_limit_sleep = 0.2

    websocket_channels = {
        L2_BOOK: 'level2',
        L3_BOOK: 'full',
        TRADES: 'matches',
        TICKER: 'ticker',
    }
    rest_channels = (
        TRADES, TICKER, L2_BOOK, L3_BOOK, ORDER_INFO, ORDER_STATUS, CANDLES, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY
    )
    rest_options = {
        LIMIT: 'limit',
        MARKET: 'market',
        FILL_OR_KILL: {'time_in_force': 'FOK'},
        IMMEDIATE_OR_CANCEL: {'time_in_force': 'IOC'},
        MAKER_OR_CANCEL: {'post_only': 1},
    }

    @classmethod
    def timestamp_normalize(ts: dt) -> float:
        return ts.timestamp()

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            sym = Symbol(entry['base_currency'], entry['quote_currency'])
            info['tick_size'][sym.normalized] = entry['quote_increment']
            info['instrument_type'][sym.normalized] = sym.type
            ret[sym.normalized] = entry['id']
        return ret, info

    def __init__(self, callbacks=None, **kwargs):
        super().__init__('wss://ws-feed.pro.coinbase.com', callbacks=callbacks, **kwargs)
        # we only keep track of the L3 order book if we have at least one subscribed order-book callback.
        # use case: subscribing to the L3 book plus Trade type gives you order_type information (see _received below),
        # and we don't need to do the rest of the book-keeping unless we have an active callback
        self.keep_l3_book = False
        if callbacks and L3_BOOK in callbacks:
            self.keep_l3_book = True
        self.__reset()

    def __reset(self, symbol=None):
        if symbol:
            self.seq_no[symbol] = None
            self.order_map.pop(symbol, None)
            self.order_type_map.pop(symbol, None)
            self.l3_book.pop(symbol, None)
            self.l2_book.pop(symbol, None)
        else:
            self.order_map = {}
            self.order_type_map = {}
            self.seq_no = None
            # sequence number validation only works when the FULL data stream is enabled
            chan = self.std_channel_to_exchange(L3_BOOK)
            if chan in self.subscription:
                pairs = self.subscription[chan]
                self.seq_no = {pair: None for pair in pairs}
            self.l3_book = {}
            self.l2_book = {}

    async def _ticker(self, msg: dict, timestamp: float):
        '''
        {
            'type': 'ticker',
            'sequence': 5928281084,
            'product_id': 'BTC-USD',
            'price': '8500.01000000',
            'open_24h': '8217.24000000',
            'volume_24h': '4529.1293778',
            'low_24h': '8172.00000000',
            'high_24h': '8600.00000000',
            'volume_30d': '329178.93594133',
            'best_bid': '8500',
            'best_ask': '8500.01'
        }

        {
            'type': 'ticker',
            'sequence': 5928281348,
            'product_id': 'BTC-USD',
            'price': '8500.00000000',
            'open_24h': '8217.24000000',
            'volume_24h': '4529.13179472',
            'low_24h': '8172.00000000',
            'high_24h': '8600.00000000',
            'volume_30d': '329178.93835825',
            'best_bid': '8500',
            'best_ask': '8500.01',
            'side': 'sell',
            'time': '2018-05-21T00:30:11.587000Z',
            'trade_id': 43736677,
            'last_size': '0.00241692'
        }
        '''
        await self.callback(TICKER, feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['product_id']),
                            bid=Decimal(msg['best_bid']),
                            ask=Decimal(msg['best_ask']),
                            timestamp=timestamp_normalize(self.id, msg['time']),
                            receipt_timestamp=timestamp)

    async def _book_update(self, msg: dict, timestamp: float):
        '''
        {
            'type': 'match', or last_match
            'trade_id': 43736593
            'maker_order_id': '2663b65f-b74e-4513-909d-975e3910cf22',
            'taker_order_id': 'd058d737-87f1-4763-bbb4-c2ccf2a40bde',
            'side': 'buy',
            'size': '0.01235647',
            'price': '8506.26000000',
            'product_id': 'BTC-USD',
            'sequence': 5928276661,
            'time': '2018-05-21T00:26:05.585000Z'
        }
        '''
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        ts = timestamp_normalize(self.id, msg['time'])

        if self.keep_l3_book and 'full' in self.subscription and pair in self.subscription['full']:
            delta = {BID: [], ASK: []}
            price = Decimal(msg['price'])
            side = ASK if msg['side'] == 'sell' else BID
            size = Decimal(msg['size'])
            maker_order_id = msg['maker_order_id']

            _, new_size = self.order_map[maker_order_id]
            new_size -= size
            if new_size <= 0:
                del self.order_map[maker_order_id]
                self.order_type_map.pop(maker_order_id, None)
                delta[side].append((maker_order_id, price, 0))
                del self.l3_book[pair][side][price][maker_order_id]
                if len(self.l3_book[pair][side][price]) == 0:
                    del self.l3_book[pair][side][price]
            else:
                self.order_map[maker_order_id] = (price, new_size)
                self.l3_book[pair][side][price][maker_order_id] = new_size
                delta[side].append((maker_order_id, price, new_size))

            await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, ts, timestamp)

        order_type = self.order_type_map.get(msg['taker_order_id'])
        await self.callback(TRADES,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['product_id']),
                            order_id=msg['trade_id'],
                            side=SELL if msg['side'] == 'buy' else BUY,
                            amount=Decimal(msg['size']),
                            price=Decimal(msg['price']),
                            timestamp=ts,
                            receipt_timestamp=timestamp,
                            order_type=order_type
                            )

    async def _pair_level2_snapshot(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        self.l2_book[pair] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['bids']
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['asks']
            })
        }

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp, timestamp)

    async def _pair_level2_update(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        ts = timestamp_normalize(self.id, msg['time'])
        delta = {BID: [], ASK: []}
        for side, price, amount in msg['changes']:
            side = BID if side == 'buy' else ASK
            price = Decimal(price)
            amount = Decimal(amount)
            bidask = self.l2_book[pair][side]

            if amount == 0:
                del bidask[price]
                delta[side].append((price, 0))
            else:
                bidask[price] = amount
                delta[side].append((price, amount))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, ts, timestamp)

    async def _book_snapshot(self, pairs: list):
        # Coinbase needs some time to send messages to us
        # before we request the snapshot. If we don't sleep
        # the snapshot seq no could be much earlier than
        # the subsequent messages, causing a seq no mismatch.
        await asyncio.sleep(2)

        url = 'https://api.pro.coinbase.com/products/{}/book?level=3'
        urls = [url.format(pair) for pair in pairs]

        results = []
        for url in urls:
            ret = await self.http_conn.read(url)
            results.append(ret)
            # rate limit - 3 per second
            await asyncio.sleep(0.3)

        timestamp = time.time()
        for res, pair in zip(results, pairs):
            orders = json.loads(res, parse_float=Decimal)
            npair = self.exchange_symbol_to_std_symbol(pair)
            self.l3_book[npair] = {BID: sd(), ASK: sd()}
            self.seq_no[npair] = orders['sequence']
            for side in (BID, ASK):
                for price, size, order_id in orders[side + 's']:
                    price = Decimal(price)
                    size = Decimal(size)
                    if price in self.l3_book[npair][side]:
                        self.l3_book[npair][side][price][order_id] = size
                    else:
                        self.l3_book[npair][side][price] = {order_id: size}
                    self.order_map[order_id] = (price, size)
            await self.book_callback(self.l3_book[npair], L3_BOOK, npair, True, None, timestamp, timestamp)

    async def _open(self, msg: dict, timestamp: float):
        if not self.keep_l3_book:
            return
        delta = {BID: [], ASK: []}
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        size = Decimal(msg['remaining_size'])
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        order_id = msg['order_id']
        ts = timestamp_normalize(self.id, msg['time'])

        if price in self.l3_book[pair][side]:
            self.l3_book[pair][side][price][order_id] = size
        else:
            self.l3_book[pair][side][price] = {order_id: size}
        self.order_map[order_id] = (price, size)

        delta[side].append((order_id, price, size))

        await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, ts, timestamp)

    async def _done(self, msg: dict, timestamp: float):
        """
        per Coinbase API Docs:

        A done message will be sent for received orders which are fully filled or canceled due
        to self-trade prevention. There will be no open message for such orders. Done messages
        for orders which are not on the book should be ignored when maintaining a real-time order book.
        """
        if 'price' not in msg:
            return

        order_id = msg['order_id']
        self.order_type_map.pop(order_id, None)
        if order_id not in self.order_map:
            return

        del self.order_map[order_id]
        if self.keep_l3_book:
            delta = {BID: [], ASK: []}

            price = Decimal(msg['price'])
            side = ASK if msg['side'] == 'sell' else BID
            pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
            ts = timestamp_normalize(self.id, msg['time'])

            del self.l3_book[pair][side][price][order_id]
            if len(self.l3_book[pair][side][price]) == 0:
                del self.l3_book[pair][side][price]
            delta[side].append((order_id, price, 0))

            await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, ts, timestamp)

    async def _received(self, msg: dict, timestamp: float):
        """
        per Coinbase docs:
        A valid order has been received and is now active. This message is emitted for every single
        valid order as soon as the matching engine receives it whether it fills immediately or not.

        This message is the only time we receive the order type (limit vs market) for a given order,
        so we keep it in a map by order ID.
        """
        order_id = msg["order_id"]
        order_type = msg["order_type"]
        self.order_type_map[order_id] = order_type

    async def _change(self, msg: dict, timestamp: float):
        """
        Like done, these updates can be sent for orders that are not in the book. Per the docs:

        Not all done or change messages will result in changing the order book. These messages will
        be sent for received orders which are not yet on the order book. Do not alter
        the order book for such messages, otherwise your order book will be incorrect.
        """
        if not self.keep_l3_book:
            return

        delta = {BID: [], ASK: []}

        if 'price' not in msg or not msg['price']:
            return

        order_id = msg['order_id']
        if order_id not in self.order_map:
            return

        ts = timestamp_normalize(self.id, msg['time'])
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        new_size = Decimal(msg['new_size'])
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])

        self.l3_book[pair][side][price][order_id] = new_size
        self.order_map[order_id] = (price, new_size)

        delta[side].append((order_id, price, new_size))

        await self.book_callback(self.l3_book, L3_BOOK, pair, False, delta, ts, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        # PERF perf_start(self.id, 'msg')
        msg = json.loads(msg, parse_float=Decimal)
        if self.seq_no:
            if 'product_id' in msg and 'sequence' in msg:
                pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
                if not self.seq_no.get(pair, None):
                    return
                if msg['sequence'] <= self.seq_no[pair]:
                    return
                if msg['sequence'] != self.seq_no[pair] + 1:
                    LOG.warning("%s: Missing sequence number detected for %s. Received %d, expected %d", self.id, pair, msg['sequence'], self.seq_no[pair] + 1)
                    LOG.warning("%s: Resetting data for %s", self.id, pair)
                    self.__reset(symbol=pair)
                    await self._book_snapshot([pair])
                    return

                self.seq_no[pair] = msg['sequence']

        if 'type' in msg:
            if msg['type'] == 'ticker':
                await self._ticker(msg, timestamp)
            elif msg['type'] == 'match' or msg['type'] == 'last_match':
                await self._book_update(msg, timestamp)
            elif msg['type'] == 'snapshot':
                await self._pair_level2_snapshot(msg, timestamp)
            elif msg['type'] == 'l2update':
                await self._pair_level2_update(msg, timestamp)
            elif msg['type'] == 'open':
                await self._open(msg, timestamp)
            elif msg['type'] == 'done':
                await self._done(msg, timestamp)
            elif msg['type'] == 'change':
                await self._change(msg, timestamp)
            elif msg['type'] == 'received':
                await self._received(msg, timestamp)
            elif msg['type'] == 'activate':
                pass
            elif msg['type'] == 'subscriptions':
                pass
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
            # PERF perf_end(self.id, 'msg')
            # PERF perf_log(self.id, 'msg')

    async def subscribe(self, conn: AsyncConnection, symbol=None):
        self.__reset(symbol=symbol)

        for chan in self.subscription:
            await conn.write(json.dumps({"type": "subscribe",
                                         "product_ids": self.subscription[chan],
                                         "channels": [chan]
                                         }))

        chan = self.std_channel_to_exchange(L3_BOOK)
        if chan in self.subscription:
            await self._book_snapshot(self.subscription[chan])

    ### REST Endpoints
    def _order_status(self, data: dict):
        if 'status' not in data:
            raise UnexpectedMessage(f"Message from exchange: {data}")
        status = data['status']
        if data['status'] == 'done' and data['done_reason'] == 'canceled':
            status = PARTIAL
        elif data['status'] == 'done':
            status = FILLED
        elif data['status'] == 'open':
            status = OPEN
        elif data['status'] == 'pending':
            status = PENDING
        elif data['status'] == CANCELLED:
            status = CANCELLED

        if 'price' not in data:
            price = Decimal(data['executed_value']) / Decimal(data['filled_size'])
        else:
            price = Decimal(data['price'])

        return {
            'order_id': data['id'],
            'symbol': data['product_id'],
            'side': BUY if data['side'] == 'buy' else SELL,
            'order_type': LIMIT if data['type'] == 'limit' else MARKET,
            'price': price,
            'total': Decimal(data['size']),
            'executed': Decimal(data['filled_size']),
            'pending': Decimal(data['size']) - Decimal(data['filled_size']),
            'timestamp': data['done_at'].timestamp() if 'done_at' in data else data['created_at'].timestamp(),
            'order_status': status
        }

    def _generate_signature(self, endpoint: str, method: str, body=''):
        timestamp = str(time.time())
        message = ''.join([timestamp, method, endpoint, body])
        hmac_key = base64.b64decode(self.config.key_secret)
        signature = hmac.new(hmac_key, message.encode('ascii'), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        return {
            'CB-ACCESS-KEY': self.config.key_id,  # The api key as a string.
            'CB-ACCESS-SIGN': signature_b64,  # The base64-encoded signature (see Signing a Message).
            'CB-ACCESS-TIMESTAMP': timestamp,  # A timestamp for your request.
            'CB-ACCESS-PASSPHRASE': self.key_passphrase,  # The passphrase you specified when creating the API key
            'Content-Type': 'Application/JSON',
        }

    def _request(self, method: str, endpoint: str, auth: bool = False, body=None, retry=None, retry_wait=0):
        api = self.sandbox_api if self.sandbox else self.api

        @request_retry(self.id, retry, retry_wait, self.log)
        def helper(verb, api, endpoint, body, auth):
            header = None
            if auth:
                header = self._generate_signature(endpoint, verb, body=json.dumps(body) if body else '')

            if method == "GET":
                return requests.get(f'{api}{endpoint}', headers=header)
            elif method == 'POST':
                return requests.post(f'{api}{endpoint}', json=body, headers=header)
            elif method == 'DELETE':
                return requests.delete(f'{api}{endpoint}', headers=header)

        return helper(method, api, endpoint, body, auth)

    def _date_to_trade(self, symbol: str, date: pd.Timestamp) -> int:
        """
        Coinbase uses trade ids to query historical trades, so
        need to search for the start date
        """
        upper = self._request('GET', f'/products/{symbol}/trades')
        upper = json.loads(upper.text, parse_float=Decimal)[0]['trade_id']
        lower = 0
        bound = (upper - lower) // 2
        while True:
            r = self._request('GET', f'/products/{symbol}/trades?after={bound}')
            if r.status_code == 429:
                time.sleep(10)
                continue
            elif r.status_code != 200:
                self.log.warning("Error %s: %s", r.status_code, r.text)
                time.sleep(60)
                continue
            data = json.loads(r.text, parse_float=Decimal)
            data = list(reversed(data))
            if len(data) == 0:
                return bound
            if data[0]['time'] <= date <= data[-1]['time']:
                for idx in range(len(data)):
                    d = pd.Timestamp(data[idx]['time'])
                    if d >= date:
                        return data[idx]['trade_id']
            else:
                if date > pd.Timestamp(data[0]['time']):
                    lower = bound
                    bound = (upper + lower) // 2
                else:
                    upper = bound
                    bound = (upper + lower) // 2
            time.sleep(RATE_LIMIT_SLEEP)

    def _trade_normalize(self, symbol: str, data: dict) -> dict:
        return {
            'timestamp': data['time'].timestamp(),
            'symbol': symbol,
            'id': data['trade_id'],
            'feed': self.id,
            'side': SELL if data['side'] == 'buy' else BUY,
            'amount': Decimal(data['size']),
            'price': Decimal(data['price']),
        }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        if end and not start:
            start = '2014-12-01'
        if start:
            if not end:
                end = pd.Timestamp.utcnow()
            start_id = self._date_to_trade(symbol, pd.Timestamp(start, tzinfo=UTC))
            end_id = self._date_to_trade(symbol, pd.Timestamp(end, tzinfo=UTC))
            while True:
                limit = 100
                start_id += 100
                if start_id > end_id:
                    limit = 100 - (start_id - end_id)
                    start_id = end_id
                if limit > 0:
                    r = self._request('GET', f'/products/{symbol}/trades?after={start_id}&limit={limit}', retry=retry, retry_wait=retry_wait)
                    if r.status_code == 429:
                        time.sleep(10)
                        continue
                    elif r.status_code != 200:
                        self.log.warning("Error %s: %s", r.status_code, r.text)
                        time.sleep(60)
                        continue
                    data = json.loads(r.text, parse_float=Decimal)
                    try:
                        data = list(reversed(data))
                    except Exception:
                        self.log.warning("Error %s: %s", r.status_code, r.text)
                        sleep(60)
                        continue
                else:
                    break

                yield list(map(lambda x: self._trade_normalize(symbol, x), data))
                if start_id >= end_id:
                    break
        else:
            data = self._request('GET', f"/products/{symbol}/trades", retry=retry, retry_wait=retry_wait)
            data = json.loads(data.text, parse_float=Decimal)
            yield [self._trade_normalize(symbol, d) for d in data]

    def ticker(self, symbol: str, retry=None, retry_wait=10):
        data = self._request('GET', f'/products/{symbol}/ticker', retry=retry, retry_wait=retry_wait)
        self._handle_error(data)
        data = json.loads(data.text, parse_float=Decimal)
        return {'symbol': symbol,
                'feed': self.id,
                'bid': Decimal(data['bid']),
                'ask': Decimal(data['ask'])
                }

    def _book(self, symbol: str, level: int, retry, retry_wait):
        data = self._request('GET', f'/products/{symbol}/book?level={level}', retry=retry, retry_wait=retry_wait)
        return json.loads(data.text, parse_float=Decimal)

    def l2_book(self, symbol: str, retry=None, retry_wait=10):
        data = self._book(symbol, 2, retry, retry_wait)
        return {
            BID: sd({
                Decimal(u[0]): Decimal(u[1])
                for u in data['bids']
            }),
            ASK: sd({
                Decimal(u[0]): Decimal(u[1])
                for u in data['asks']
            })
        }

    def l3_book(self, symbol: str, retry=None, retry_wait=10):
        orders = self._book(symbol, 3, retry, retry_wait)
        ret = {BID: sd({}), ASK: sd({})}
        for side in (BID, ASK):
            for price, size, order_id in orders[side + 's']:
                price = Decimal(price)
                size = Decimal(size)
                if price in ret[side]:
                    ret[side][price][order_id] = size
                else:
                    ret[side][price] = {order_id: size}
        return ret

    def balances(self):
        resp = self._request('GET', "/accounts", auth=True)
        self._handle_error(resp)
        return {
            entry['currency']: {
                'total': Decimal(entry['balance']),
                'available': Decimal(entry['available'])
            }
            for entry in json.loads(resp.text, parse_float=Decimal)
        }

    def orders(self):
        endpoint = "/orders"
        data = self._request("GET", endpoint, auth=True)
        data = json.loads(data.text, parse_float=Decimal)
        return [self._order_status(order) for order in data]

    def order_status(self, order_id: str):
        endpoint = f"/orders/{order_id}"
        order = self._request("GET", endpoint, auth=True)
        order = json.loads(order.text, parse_float=Decimal)
        return self._order_status(order)

    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, client_order_id=None, options=None):
        ot = normalize_trading_options(self.id, order_type)
        if ot == MARKET and price:
            raise ValueError('Cannot specify price on a market order')
        if ot == LIMIT and not price:
            raise ValueError('Must specify price on a limit order')

        body = {
            'product_id': symbol,
            'side': 'buy' if BUY else SELL,
            'size': str(amount),
            'type': ot
        }

        if price:
            body['price'] = str(price)
        if client_order_id:
            body['client_oid'] = client_order_id
        if options:
            _ = [body.update(normalize_trading_options(self.id, o)) for o in options]
        resp = self._request('POST', '/orders', auth=True, body=body)
        return self._order_status(json.loads(resp.text, parse_float=Decimal))

    def cancel_order(self, order_id: str):
        endpoint = f"/orders/{order_id}"
        order = self.order_status(order_id)
        data = self._request("DELETE", endpoint, auth=True)
        data = json.loads(data.text, parse_float=Decimal)
        if data[0] == order['order_id']:
            order['status'] = CANCELLED
            return order
        return data

    def trade_history(self, symbol: str, start=None, end=None):
        endpoint = f"/orders?product_id={symbol}&status=done"
        data = self._request("GET", endpoint, auth=True)
        data = json.loads(data.text, parse_float=Decimal)
        return [
            {
                'order_id': order['id'],
                'trade_id': order['id'],
                'side': BUY if order['side'] == 'buy' else SELL,
                'price': Decimal(order['executed_value']) / Decimal(order['filled_size']),
                'amount': Decimal(order['filled_size']),
                'timestamp': order['done_at'].timestamp(),
                'fee_amount': Decimal(order['fill_fees']),
                'fee_currency': symbol.split('-')[1]
            }
            for order in data
        ]

    def _candle_normalize(self, symbol: str, data: list) -> dict:
        candle_position_names = ('time', 'low', 'high', 'open', 'close', 'volume')
        res = {'symbol': symbol, 'feed': self.id}
        for i, name in enumerate(candle_position_names):
            if name == 'time':
                res['timestamp'] = data[i]
            else:
                res[name] = Decimal(data[i])
        return res

    def _to_isoformat(self, dt: pd.Timestamp):
        """Required as cryptostore doesnt allow +00:00 for UTC requires Z explicitly.
        """
        return dt.isoformat().replace("+00:00", 'Z')

    def candles(self, symbol: str, start: Optional[Union[str, pd.Timestamp]] = None, end: Optional[Union[str, pd.Timestamp]] = None, granularity: Optional[Union[pd.Timedelta, int]] = 3600, retry=None, retry_wait=10):
        """
        Historic rate OHLC candles
        [
            [ time, low, high, open, close, volume ],
            [ 1415398768, 0.32, 4.2, 0.35, 4.2, 12.3 ],
            ...
        ]
        Parameters
        ----------
        :param symbol: the symbol to query data for e.g. BTC-USD
        :param start: the start time (optional)
        :param end: the end time (optional)
        :param granularity: in seconds (int) or a specified pandas timedelta. This field must be one of the following values: {60, 300, 900, 3600, 21600, 86400}
        If data points are readily available, your response may contain as many as 300
        candles and some of those candles may precede your declared start value.

        The maximum number of data points for a single request is 300 candles.
        If your selection of start/end time and granularity will result in more than
        300 data points, your request will be rejected. If you wish to retrieve fine
        granularity data over a larger time range, you will need to make multiple
        requests with new start/end ranges
        """
        limit = 300  # return max of 300 rows per request

        # Check granularity
        if isinstance(granularity, pd.Timedelta):
            granularity = granularity.total_seconds()
        granularity = int(granularity)
        assert granularity in {60, 300, 900, 3600, 21600, 86400}, 'Granularity must be in {60, 300, 900, 3600, 21600, 86400} as per https://docs.pro.coinbase.com/#get-historic-rates'
        td = pd.to_timedelta(granularity, unit='s')

        if end and not start:
            start = '2014-12-01'
        if start:
            if not end:
                end = pd.Timestamp.utcnow().tz_localize(None)

            start_id = pd.to_datetime(start, utc=True).floor(td)
            end_id_max = pd.to_datetime(end, utc=True).ceil(td)
            self.log.info(f"candles - stepping through {symbol} ({start}, {end}) where step = {td}")
            while True:

                end_id = start_id + (limit - 1) * td
                if end_id > end_id_max:
                    end_id = end_id_max
                if start_id > end_id_max:
                    break

                url = f'/products/{symbol}/candles?granularity={granularity}&start={self._to_isoformat(start_id)}&end={self._to_isoformat(end_id)}'
                self.log.debug(url)
                r = self._request('GET', url, retry=retry, retry_wait=retry_wait)
                if r.status_code == 429:
                    time.sleep(10)
                    continue
                elif r.status_code != 200:
                    self.log.warning("Error %s: %s", r.status_code, r.text)
                    time.sleep(60)
                    continue

                data = json.loads(r.text, parse_float=Decimal)

                try:
                    data = list(reversed(data))
                except Exception:
                    self.log.warning("Error %s: %s", r.status_code, r.text)
                    time.sleep(60)
                    continue
                yield list(map(lambda x: self._candle_normalize(symbol, x), data))
                time.sleep(self.rate_limit_sleep * 4)
                start_id = end_id + td
        else:
            data = self._request('GET', f"/products/{symbol}/candles", retry=retry, retry_wait=retry_wait)
            data = json.loads(data.text, parse_float=Decimal)
            yield [self._candle_normalize(symbol, d) for d in data]
