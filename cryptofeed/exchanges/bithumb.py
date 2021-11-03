'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Tuple, Dict
from datetime import datetime as dt
from datetime import timedelta

from yapic import json

from cryptofeed.symbols import Symbol, Symbols
from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BUY, BITHUMB, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.types import Trade


LOG = logging.getLogger('feedhandler')


class Bithumb(Feed):
    '''
    Before you use this bithumb implementation, you should know that this is exchange's API is pretty terrible.

    For some unknown reason, bithumb's api_info page lists all their KRW symbols as USDT. Probably because they bought
    the exchange and copied everything but didn't bother to update the reference data.

    We'll just assume that anything USDT is actually KRW. A search on their exchange page
    shows that there is no USDT symbols available. Please be careful when referencing their api_info page
    '''
    id = BITHUMB
    api = "https://api.bithumb.com/public"
    symbol_endpoint = [
        ('https://api.bithumb.com/public/ticker/ALL_BTC', 'BTC'),
        ('https://api.bithumb.com/public/ticker/ALL_KRW', 'KRW')
    ]
    websocket_channels = {
        # L2_BOOK: 'orderbookdepth', <-- technically the exchange supports orderbooks but it only provides orderbook deltas, there is
        # no way to synchronize against a rest snapshot, nor request/obtain an orderbook via the websocket, so this isn't really useful
        TRADES: 'transaction',
    }

    @classmethod
    def timestamp_normalize(cls, ts: dt) -> float:
        return (ts - timedelta(hours=9)).timestamp()

    # Override symbol_mapping class method, because this bithumb is a very special case.
    # There is no actual page in the API for reference info.
    # Need to query the ticker endpoint by quote currency for that info
    # To qeury the ticker endpoint, you need to know which quote currency you want. So far, seems like the exhcnage
    # only offers KRW and BTC as quote currencies.
    @classmethod
    def symbol_mapping(cls, refresh=False) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            LOG.debug("%s: reading symbol information from %s", cls.id, cls.symbol_endpoint)
            data = {}
            for ep, quote_curr in cls.symbol_endpoint:
                data[quote_curr] = cls.http_sync.read(ep, json=True, uuid=cls.id)

            syms, info = cls._parse_symbol_data(data)
            Symbols.set(cls.id, syms, info)
            return syms
        except Exception as e:
            LOG.error("%s: Failed to parse symbol information: %s", cls.id, str(e), exc_info=True)
            raise

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}

        for quote_curr, response in data.items():
            bases = response['data']
            for base_curr in bases.keys():
                if base_curr == 'date':
                    continue
                s = Symbol(base_curr, quote_curr)
                ret[s.normalized] = f"{base_curr}_{quote_curr}"
                info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, max_depth=30, **kwargs):
        super().__init__("wss://pubwss.bithumb.com/pub/ws", max_depth=max_depth, **kwargs)

    async def _trades(self, msg: dict, rtimestamp: float):
        '''
        {
            "type": "transaction",
            "content": {
                "list": [
                    {
                        "symbol": "BTC_KRW", // currency code
                        "buySellGb": "1", // type of contract (1: sale contract, 2: buy contract)
                        "contPrice": "10579000", // execution price
                        "contQty": "0.01", // number of contracts
                        "contAmt": "105790.00", // execution amount
                        "contDtm": "2020-01-29 12:24:18.830039", // Signing time
                        "updn": "dn" // comparison with the previous price: up-up, dn-down
                    }
                ]
            }
        }
        '''
        trades = msg.get('content', {}).get('list', [])

        for trade in trades:
            # API ref list uses '-', but market data returns '_'
            symbol = self.exchange_symbol_to_std_symbol(trade['symbol'])
            timestamp = self.timestamp_normalize(trade['contDtm'])
            price = Decimal(trade['contPrice'])
            quantity = Decimal(trade['contQty'])
            side = BUY if trade['buySellGb'] == '2' else SELL

            t = Trade(self.id, symbol, side, quantity, price, timestamp, raw=trade)
            await self.callback(TRADES, t, rtimestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        msg_type = msg.get('type', None)

        if msg_type == 'transaction':
            await self._trades(msg, timestamp)
        elif msg_type is None and msg.get('status', None) == '0000':
            return
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        if self.subscription:
            for chan in self.subscription:
                await conn.write(json.dumps({
                    "type": chan,
                    "symbols": [symbol for symbol in self.subscription[chan]]
                    # API ref list uses '-', but subscription requires '_'
                }))
