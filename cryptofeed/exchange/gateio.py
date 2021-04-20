'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
import time
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, GATEIO, L2_BOOK, TICKER, TRADES, BUY, SELL
from cryptofeed.feed import Feed


LOG = logging.getLogger('feedhandler')


class Gateio(Feed):
    id = GATEIO
    symbol_endpoint = "https://api.gateio.ws/api/v4/spot/currency_pairs"

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        return {data["id"].replace("_", symbol_separator): data['id'] for data in data if data["trade_status"] == "tradable"}, {}

    def __init__(self, **kwargs):
        super().__init__('wss://api.gateio.ws/ws/v4/', **kwargs)

    def _reset(self):
        self.l2_book = {}

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            'time': 1618876417,
            'channel': 'spot.tickers',
            'event': 'update',
            'result': {
                'currency_pair': 'BTC_USDT',
                'last': '55636.45',
                'lowest_ask': '55634.06',
                'highest_bid': '55634.05',
                'change_percentage': '-0.7634',
                'base_volume': '1138.9062880772',
                'quote_volume': '63844439.342660318028',
                'high_24h': '63736.81',
                'low_24h': '50986.18'
            }
        }
        """
        await self.callback(TICKER, feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['result']['currency_pair']),
                            bid=Decimal(msg['result']['highest_bid']),
                            ask=Decimal(msg['result']['lowest_ask']),
                            timestamp=float(msg['time']),
                            receipt_timestamp=timestamp)

    async def _trades(self, msg: dict, timestamp: float):
        """
        {
            "time": 1606292218,
            "channel": "spot.trades",
            "event": "update",
            "result": {
                "id": 309143071,
                "create_time": 1606292218,
                "create_time_ms": "1606292218213.4578",
                "side": "sell",
                "currency_pair": "GT_USDT",
                "amount": "16.4700000000",
                "price": "0.4705000000"
            }
        }
        """
        await self.callback(TRADES, feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['result']['currency_pair']),
                            side=SELL if msg['result']['side'] == 'sell' else BUY,
                            amount=Decimal(msg['result']['amount']),
                            price=Decimal(msg['result']['price']),
                            timestamp=float(msg['result']['create_time_ms']) / 1000,
                            receipt_timestamp=timestamp,
                            order_id=msg['result']['id'])

    async def _l2_book(self, msg: dict, timestamp: float):
        """
        {
            'method': 'depth.update',
            'params': [
                    True,   <- true = full book, false = update
                    {
                        'asks': [['11681.19', '0.15'], ['11681.83', '0.0049'], ['11682.06', '0.005'], ['11682.25', '0.4663'], ['11682.33', '0.002'], ['11682.5', '0.0001'], ['11682.9', '0.0047'], ['11683.7', '0.7506'], ['11684.46', '0.1076'], ['11684.53', '0.3244'], ['11685', '0.0001'], ['11685.19', '0.00034298'], ['11685.31', '0.00038961'], ['11686.99', '0.144'], ['11687', '0.023'], ['11687.27', '0.1227'], ['11687.3', '0.011'], ['11687.5', '0.0001'], ['11688', '0.2078'], ['11689.69', '0.1787'], ['11689.91', '0.0893'], ['11690', '0.0001'], ['11690.32', '0.0446'], ['11690.47', '0.1087'], ['11690.52', '0.1785'], ['11691.27', '0.0034'], ['11691.39', '0.3'], ['11692.26', '0.2'], ['11692.3', '0.00109695'], ['11692.5', '0.0001']],
                        'bids': [['11680.86', '0.0089'], ['11680.24', '0.0082'], ['11679.09', '0.7506'], ['11678.48', '0.0342'], ['11675.11', '0.288'], ['11674.97', '0.0342'], ['11674.61', '0.1105'], ['11674.34', '0.18'], ['11673.98', '0.0446'], ['11673.88', '0.3'], ['11673.67', '0.1785'], ['11671.46', '0.0342'], ['11669.72', '0.1112'], ['11669.59', '0.04354248'], ['11668.91', '0.2'], ['11668.78', '0.80535358'], ['11667.95', '0.0342'], ['11666.71', '0.2066'], ['11666.48', '0.04202993'], ['11665.65', '0.01'], ['11664.44', '0.0342'], ['11663.97', '0.428'], ['11660.94', '0.0343'], ['11660.86', '0.2'], ['11660.1', '0.3'], ['11657.44', '0.0219'], ['11657.07', '0.3'], ['11656.96', '0.3'], ['11655.8', '0.1027'], ['11655.36', '0.2098']]
                    },
                    'BTC_USDT'
                ],
                'id': None
            }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['params'][-1])
        forced = msg['params'][0]
        delta = {BID: [], ASK: []}

        if forced:
            self.l2_book[symbol] = {BID: sd(), ASK: sd()}
        data = msg['params'][1]

        for side, exchange_key in [(BID, 'bids'), (ASK, 'asks')]:
            if exchange_key in data:
                for entry in data[exchange_key]:
                    price = Decimal(entry[0])
                    amount = Decimal(entry[1])

                    if amount == 0:
                        del self.l2_book[symbol][side][price]
                    else:
                        self.l2_book[symbol][side][price] = amount

                    delta[side].append((price, amount))
        await self.book_callback(self.l2_book[symbol], L2_BOOK, symbol, forced, delta, timestamp, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if "error" in msg:
            if msg['error'] is None:
                pass
            else:
                LOG.warning("%s: Error received from exchange - %s", self.id, msg)
        if msg['event'] == 'subscribe':
            return
        elif 'channel' in msg:
            market, channel = msg['channel'].split('.')
            if channel == 'tickers':
                await self._ticker(msg, timestamp)
            elif channel == 'trades':
                await self._trades(msg, timestamp)
            # elif msg['method'] == 'depth.update':
            #     await self._l2_book(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self._reset()
        for chan in set(self.channels or self.subscription):
            pairs = set(self.symbols or self.subscription[chan])
            if 'depth' in chan:
                pairs = [[pair, 30, "0.00000001"] for pair in pairs]

            await conn.write(json.dumps(
                {
                    "time": int(time.time()),
                    "channel": chan,
                    "event": 'subscribe',
                    "payload": pairs,
                }
            ))
