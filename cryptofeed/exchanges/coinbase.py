'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hashlib
import hmac
import logging
import time
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from cryptofeed import _json as json

from cryptofeed.config import Config
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, CANDLES, COINBASE, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import Candle, OrderBook, Ticker, Trade

LOG = logging.getLogger(__name__)


def get_private_parameters(config: Config, chan: str, product_ids: list) -> dict:
    """Sign a websocket subscription. Public market data channels need no credentials, so
    when none are configured this returns nothing and the subscription goes out unsigned."""
    if not config["coinbase"]["key_id"] or not config["coinbase"]["key_secret"]:
        return {}
    timestamp = str(int(time.time()))
    message = f"{timestamp}{chan}{','.join(product_ids)}"
    signature = hmac.new(
        config["coinbase"]["key_secret"].encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return {'api_key': config["coinbase"]["key_id"], 'timestamp': timestamp, 'signature': signature}


class Coinbase(Feed):
    id = COINBASE
    websocket_endpoints = [WebsocketEndpoint('wss://advanced-trade-ws.coinbase.com', options={'compression': None})]
    rest_endpoints = [RestEndpoint('https://api.coinbase.com/api/v3/brokerage', routes=Routes('/market/products', l3book='/market/product_book?product_id={}'))]

    websocket_channels = {
        L2_BOOK: 'level2',
        TRADES: 'market_trades',
        TICKER: 'ticker',
        CANDLES: 'candles',
    }
    request_limit = 10
    # the candles channel is fixed at five minute granularity
    valid_candle_intervals = {'5m'}
    candle_interval_map = {'5m': 300}

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

    async def _ticker_update(self, msg: dict, timestamp: float, ts: str):
        '''
        {
            'type': 'ticker',
            'product_id': 'BTC-USD',
            'price': '65093.36',
            'volume_24_h': '2860.31872502',
            'low_24_h': '64675.22', 'high_24_h': '65252.99',
            'low_52_w': '57717.55', 'high_52_w': '126296',
            'price_percent_chg_24_h': '0.09772441285005',
            'best_bid': '65093.36', 'best_ask': '65093.37',
            'best_bid_quantity': '0.15298222', 'best_ask_quantity': '0.19057584'
        }
        '''
        t = Ticker(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['product_id']),
            Decimal(msg['best_bid']),
            Decimal(msg['best_ask']),
            self.timestamp_normalize(ts),
            raw=msg
        )
        await self.callback(TICKER, t, timestamp)

    async def _candle_update(self, msg: dict, timestamp: float, ts: str):
        '''
        {
            'start': '1786269300',
            'high': '64836.04', 'low': '64799.98',
            'open': '64804.5', 'close': '64832.31',
            'volume': '3.70089188',
            'product_id': 'BTC-USD'
        }

        The channel only publishes five minute candles, and does not flag the final update
        of an interval - closed is therefore reported as False for every update.
        '''
        start = float(msg['start'])
        interval = self.candle_interval_map[self.candle_interval]
        c = Candle(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['product_id']),
            start,
            start + interval - 1,
            self.candle_interval,
            None,
            Decimal(msg['open']),
            Decimal(msg['close']),
            Decimal(msg['high']),
            Decimal(msg['low']),
            Decimal(msg['volume']),
            False,
            self.timestamp_normalize(ts),
            raw=msg
        )
        await self.callback(CANDLES, c, timestamp)

    async def _pair_level2_snapshot(self, msg: dict, timestamp: float, ts: str):
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

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(ts), raw=msg)

    async def _pair_level2_update(self, msg: dict, timestamp: float, ts: str):
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

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(ts), raw=msg, delta=delta)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
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
                        await self._pair_level2_snapshot(event, timestamp, msg['timestamp'])
                elif msg['channel'] == 'ticker':
                    for ticker in event['tickers']:
                        await self._ticker_update(ticker, timestamp, msg['timestamp'])
                elif msg['channel'] == 'candles':
                    for candle in event['candles']:
                        await self._candle_update(candle, timestamp, msg['timestamp'])
                elif msg['channel'] in ('subscriptions', 'heartbeats'):
                    pass
                else:
                    LOG.warning("%s: Invalid message type %s", self.id, msg)

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

        await _subscribe('heartbeats', all_pairs)
