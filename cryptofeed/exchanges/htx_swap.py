'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from cryptofeed.symbols import Symbol, str_to_symbol
import logging
import time
import zlib
from decimal import Decimal
from typing import Dict, Tuple

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BUY, FUNDING, HTX_SWAP, L2_BOOK, PERPETUAL, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.types import Funding, OrderBook, Trade


LOG = logging.getLogger(__name__)


class HTXSwap(Feed):
    id = HTX_SWAP
    book_delivery = 'snapshot'
    websocket_endpoints = [
        WebsocketEndpoint('wss://api.hbdm.com/swap-ws', instrument_filter=('QUOTE', ('USD',))),
        WebsocketEndpoint('wss://api.hbdm.com/linear-swap-ws', instrument_filter=('QUOTE', ('USDT',)))
    ]
    rest_endpoints = [
        RestEndpoint('https://api.hbdm.com', routes=Routes('/swap-api/v1/swap_contract_info', funding='/swap-api/v1/swap_batch_funding_rate'), instrument_filter=('QUOTE', ('USD',))),
        RestEndpoint('https://api.hbdm.com', routes=Routes('/linear-swap-api/v1/swap_contract_info', funding='/linear-swap-api/v1/swap_batch_funding_rate'), instrument_filter=('QUOTE', ('USDT',)))
    ]
    funding_interval = 60

    websocket_channels = {
        L2_BOOK: 'depth.step0',
        TRADES: 'trade.detail',
        FUNDING: 'funding',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        for d in data:
            for e in d['data']:
                base, quote = e['contract_code'].split("-")
                s = Symbol(base, quote, type=PERPETUAL)
                ret[s.normalized] = e['contract_code']
                info['tick_size'][s.normalized] = e['price_tick']
                info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.funding_updates = {}

    def __reset(self):
        self._l2_book = {}

    async def _book(self, msg: dict, timestamp: float):
        """
        {
            'ch':'market.BTC_CW.depth.step0',
            'ts':1565857755564,
            'tick':{
                'mrid':14848858327,
                'id':1565857755,
                'bids':[
                    [  Decimal('9829.99'), 1], ...
                ]
                'asks':[
                    [ 9830, 625], ...
                ]
            },
            'ts':1565857755552,
            'version':1565857755,
            'ch':'market.BTC_CW.depth.step0'
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1])
        data = msg['tick']

        # When a pair is delisted, empty updates are still sent:
        # {'ch': 'market.AKRO-USD.depth.step0', 'ts': 1606951241196, 'tick': {'mrid': 50651100044, 'id': 1606951241, 'ts': 1606951241195, 'version': 1606951241, 'ch': 'market.AKRO-USD.depth.step0'}}
        if 'bids' in data and 'asks' in data:
            if pair not in self._l2_book:
                self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
            self._l2_book[pair].book.bids = {Decimal(price): Decimal(amount) for price, amount in data['bids']}
            self._l2_book[pair].book.asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}

            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(msg['ts']), raw=msg)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'ch': 'market.btcusd.trade.detail',
            'ts': 1549773923965,
            'tick': {
                'id': 100065340982,
                'ts': 1549757127140,
                'data': [{'id': '10006534098224147003732', 'amount': Decimal('0.0777'), 'price': Decimal('3669.69'), 'direction': 'buy', 'ts': 1549757127140}]}
        }
        """
        for trade in msg['tick']['data']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1]),
                BUY if trade['direction'] == 'buy' else SELL,
                Decimal(trade['amount']),
                Decimal(trade['price']),
                self.timestamp_normalize(trade['ts']),
                id=str(trade['id']),
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _funding(self, pairs):
        """Poll every subscribed contract's funding rate, two requests per cycle.

        {
            "status": "ok",
            "data": [{
                "estimated_rate": null,
                "funding_rate": "0.000100000000000000",
                "contract_code": "BTC-USD",
                "symbol": "BTC",
                "fee_asset": "BTC",
                "funding_time": "1786406400000",
                "next_funding_time": null
            }, ...],
            "ts": 1603866304635
        }
        """
        wanted = set(pairs)
        endpoints = [ep for ep in self.rest_endpoints
                     if any(str_to_symbol(self.exchange_symbol_to_std_symbol(pair)).quote in ep.instrument_filter[1]
                            for pair in wanted)]

        while True:
            for ep in endpoints:
                data = json.loads(await self.http_conn.read(ep.route('funding')), parse_float=Decimal)
                received = time.time()

                for entry in data['data']:
                    pair = entry['contract_code']
                    if pair not in wanted:
                        continue

                    update = (entry['funding_rate'], self.timestamp_normalize(int(entry['funding_time'])))
                    if self.funding_updates.get(pair) == update:
                        continue
                    self.funding_updates[pair] = update
                    settlement = (self.timestamp_normalize(int(entry['next_funding_time'])) if entry['next_funding_time'] else self.timestamp_normalize(int(entry['funding_time'])))
                    f = Funding(
                        self.id,
                        self.exchange_symbol_to_std_symbol(pair),
                        None,
                        Decimal(entry['funding_rate']),
                        settlement,
                        self.timestamp_normalize(int(data['ts'])),
                        predicted_rate=Decimal(entry['estimated_rate']) if entry['estimated_rate'] is not None else None,
                        raw=entry
                    )
                    await self.callback(FUNDING, f, received)

            await asyncio.sleep(self.funding_interval)

    async def message_handler(self, msg: str, conn, timestamp: float):
        # unzip message
        msg = zlib.decompress(msg, 16 + zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        if 'ping' in msg:
            await conn.write(json.dumps({'pong': msg['ping']}))
        elif 'status' in msg and msg['status'] == 'ok':
            return
        elif 'ch' in msg:
            if 'trade' in msg['ch']:
                await self._trade(msg, timestamp)
            elif 'depth' in msg['ch']:
                await self._book(msg, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        if FUNDING in self.subscription:
            self._spawn('funding', self._funding, self.subscription[FUNDING])

        self.__reset()

        client_id = 0
        for chan, symbols in conn.subscription.items():
            if self.exchange_channel_to_std(chan) == FUNDING:
                continue
            for symbol in symbols:
                client_id += 1
                await conn.write(json.dumps(
                    {
                        "sub": f"market.{symbol}.{chan}",
                        "id": str(client_id)
                    }
                ))
