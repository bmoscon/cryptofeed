'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.standards import normalize_channel
from cryptofeed.connection import AsyncConnection
from decimal import Decimal
import logging
from typing import Dict, Tuple

from yapic import json

from cryptofeed.defines import BUY, KUCOIN, SELL, TICKER, TRADES
from cryptofeed.feed import Feed


LOG = logging.getLogger('feedhandler')


class KuCoin(Feed):
    id = KUCOIN
    symbol_endpoint = 'https://api.kucoin.com/api/v1/symbols'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'tick_size': {}}
        for symbol in data['data']:
            if not symbol['enableTrading']:
                continue
            sym = symbol['symbol']
            info['tick_size'][sym] = symbol['priceIncrement']
            ret[sym] = sym
        return ret, info

    def __init__(self, **kwargs):
        address_info = self.http_sync.write('https://api.kucoin.com/api/v1/bullet-public', json=True)
        token = address_info['data']['token']
        address = address_info['data']['instanceServers'][0]['endpoint']
        address = f"{address}?token={token}"
        super().__init__(address, **kwargs)
        self.ws_defaults['ping_interval'] = address_info['data']['instanceServers'][0]['pingInterval'] / 2000
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _ticker(self, msg: dict, symbol: str, timestamp: float):
        """
        {
            "type":"message",
            "topic":"/market/ticker:BTC-USDT",
            "subject":"trade.ticker",
            "data":{

                "sequence":"1545896668986", // Sequence number
                "price":"0.08",             // Last traded price
                "size":"0.011",             //  Last traded amount
                "bestAsk":"0.08",          // Best ask price
                "bestAskSize":"0.18",      // Best ask size
                "bestBid":"0.049",         // Best bid price
                "bestBidSize":"0.036"     // Best bid size
            }
        }
        """
        await self.callback(TICKER, feed=self.id,
                            symbol=symbol,
                            bid=Decimal(msg['data']['bestBid']),
                            ask=Decimal(msg['data']['bestAsk']),
                            timestamp=timestamp,
                            receipt_timestamp=timestamp)

    async def _trades(self, msg: dict, symbol: str, timestamp: float):
        """
        {
            "type":"message",
            "topic":"/market/match:BTC-USDT",
            "subject":"trade.l3match",
            "data":{

                "sequence":"1545896669145",
                "type":"match",
                "symbol":"BTC-USDT",
                "side":"buy",
                "price":"0.08200000000000000000",
                "size":"0.01022222000000000000",
                "tradeId":"5c24c5da03aa673885cd67aa",
                "takerOrderId":"5c24c5d903aa6772d55b371e",
                "makerOrderId":"5c2187d003aa677bd09d5c93",
                "time":"1545913818099033203"
            }
        }
        """
        await self.callback(TRADES, feed=self.id,
                            symbol=symbol,
                            side=BUY if msg['data']['side'] == 'buy' else SELL,
                            amount=Decimal(msg['data']['size']),
                            price=Decimal(msg['data']['price']),
                            timestamp=float(msg['data']['time']) / 1000000000,
                            receipt_timestamp=timestamp,
                            order_id=msg['data']['tradeId'])

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in set(self.channels or self.subscription):
            symbols = set(self.symbols or self.subscription[chan])
            await conn.write(json.dumps({
                'id': 1,
                'type': 'subscribe',
                'topic': f"{chan}:{','.join(symbols)}",
                'privateChannel': False,
                'response': True
            }))

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if msg['type'] in {'welcome', 'ack'}:
            return

        topic, symbol = msg['topic'].split(":", 1)
        topic = normalize_channel(self.id, topic)

        if topic == TICKER:
            await self._ticker(msg, symbol, timestamp)
        elif topic == TRADES:
            await self._trades(msg, symbol, timestamp)
        else:
            LOG.warning("%s: Unhandled message type %s", self.id, msg)
