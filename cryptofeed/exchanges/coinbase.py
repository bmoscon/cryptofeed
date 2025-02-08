'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import datetime
import hashlib
import hmac
import logging
import time
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from yapic import json

from cryptofeed.config import Config
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, COINBASE, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.coinbase_rest import CoinbaseRestMixin
from cryptofeed.types import OrderBook, Trade

LOG = logging.getLogger('feedhandler')


def get_private_parameters(config: Config, chan: str = None, product_ids_str: list = None,
                           rest_api: bool = False, endpoint: str = None) -> dict:
    timestamp = str(int(time.time()))
    if rest_api:
        base_endpoint = '/api/v3/brokerage/'
        endpoint = base_endpoint + endpoint
        message = f'{timestamp}GET{endpoint}'
    else:
        product_ids_str = ",".join(product_ids_str)
        message = f"{timestamp}{chan}{product_ids_str}"
    signature = hmac.new(
        config["coinbase"]["key_secret"].encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    if rest_api:
        return {'CB-ACCESS-KEY': config["coinbase"]["key_id"], 'CB-ACCESS-TIMESTAMP': timestamp,
                'CB-ACCESS-SIGN': signature}
    else:
        return {'api_key': config["coinbase"]["key_id"], 'timestamp': timestamp, 'signature': signature}


class Coinbase(Feed, CoinbaseRestMixin):
    id = COINBASE
    websocket_endpoints = [WebsocketEndpoint('wss://advanced-trade-ws.coinbase.com', options={'compression': None})]
    rest_endpoints = [
        RestEndpoint('https://api.coinbase.com/api/v3/brokerage', routes=Routes('/products', l3book='/product_book?product_id={}'))]

    # TODO: implement candles and user channels
    websocket_channels = {
        L2_BOOK: 'level2',
        TRADES: 'market_trades',
    }
    request_limit = 10

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['products']:
            sym = Symbol(entry['base_currency_id'], entry['quote_currency_id'])
            info['tick_size'][sym.normalized] = entry['quote_increment']
            info['instrument_type'][sym.normalized] = sym.type
            ret[sym.normalized] = entry['product_id']
        return ret, info

    @classmethod
    def symbols(cls, config: dict = None, refresh=False) -> list:
        config = Config(config)
        if 'coinbase' not in config or 'key_id' not in config['coinbase'] or 'key_secret' not in config['coinbase']:
            raise ValueError('You must provide key_id and key_secret in config to retrieve symbols from Coinbase.')
        headers = get_private_parameters(config, rest_api=True, endpoint='products')
        return list(cls.symbol_mapping(refresh=refresh, headers=headers).keys())

    def __init__(self, callbacks=None, **kwargs):
        super().__init__(callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}

    async def _trade_update(self, msg: dict, timestamp: float):
        '''
        {
            'trade_id': 43736593
            'side': 'BUY' or 'SELL',
            'size': '0.01235647',
            'price': '8506.26000000',
            'product_id': 'BTC-USD',
            'time': '2018-05-21T00:26:05.585000Z'
        }
        '''
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        ts = self.timestamp_normalize(msg['time'])
        order_type = 'market'
        t = Trade(
            self.id,
            pair,
            SELL if msg['side'] == 'SELL' else BUY,
            Decimal(msg['size']),
            Decimal(msg['price']),
            ts,
            id=str(msg['trade_id']),
            type=order_type,
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def _pair_level2_snapshot(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        bids = {Decimal(update['price_level']): Decimal(update['new_quantity']) for update in msg['updates'] if
                update['side'] == 'bid'}
        asks = {Decimal(update['price_level']): Decimal(update['new_quantity']) for update in msg['updates'] if
                update['side'] == 'ask'}
        if pair not in self._l2_book:
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks)
        else:
            self._l2_book[pair].book.bids = bids
            self._l2_book[pair].book.asks = asks

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg)

    async def _pair_level2_update(self, msg: dict, timestamp: float, ts: datetime):
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        delta = {BID: [], ASK: []}
        for update in msg['updates']:
            side = BID if update['side'] == 'bid' else ASK
            price = Decimal(update['price_level'])
            amount = Decimal(update['new_quantity'])

            if amount == 0:
                if price in self._l2_book[pair].book[side]:
                    del self._l2_book[pair].book[side][price]
                    delta[side].append((price, 0))
            else:
                self._l2_book[pair].book[side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=ts, raw=msg, delta=delta)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        # PERF perf_start(self.id, 'msg')
        msg = json.loads(msg, parse_float=Decimal)
        if 'channel' in msg and 'events' in msg:
            for event in msg['events']:
                if msg['channel'] == 'market_trades':
                    if event.get('type') == 'update':
                        for trade in event['trades']:
                            await self._trade_update(trade, timestamp)
                    else:
                        pass  # TODO: do we want to implement trades snapshots?
                elif msg['channel'] == 'l2_data':
                    if event.get('type') == 'update':
                        await self._pair_level2_update(event, timestamp, msg['timestamp'])
                    elif event.get('type') == 'snapshot':
                        await self._pair_level2_snapshot(event, timestamp)
                elif msg['channel'] == 'subscriptions':
                    pass
                else:
                    LOG.warning("%s: Invalid message type %s", self.id, msg)
                # PERF perf_end(self.id, 'msg')
                # PERF perf_log(self.id, 'msg')

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        all_pairs = list()

        async def _subscribe(chan: str, product_ids: list):
            params = {"type": "subscribe",
                      "product_ids": product_ids,
                      "channel": chan
                      }
            private_params = get_private_parameters(self.config, chan, product_ids)
            if private_params:
                params = {**params, **private_params}
            await conn.write(json.dumps(params))

        for channel in self.subscription:
            all_pairs += self.subscription[channel]
            await _subscribe(channel, self.subscription[channel])
        all_pairs = list(dict.fromkeys(all_pairs))
        await _subscribe('heartbeat', all_pairs)
        # Implementing heartbeat as per Best Practices doc: https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-best-practices
