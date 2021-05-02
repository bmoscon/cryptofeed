'''
Huobi_DM has 3 futures per currency (with USD as base): weekly, bi-weekly(the next week), quarterly and next quarter.

You must subscribe to them with: CRY_TC
where
   CRY = BTC, ETC, etc.
   TC is the time code mapping below:
     mapping  = {
         "this_week": "CW",   # current week
         "next_week": "NW",   # next week
         "quarter": "CQ",     # current quarter
         "next_quarter": "NQ" # Next quarter

     }

So for example, to get the quarterly BTC future, you subscribe to "BTC_CQ", and it is returned to channel "market.BTC_CQ. ..."
However since the actual contract changes over time, we want to publish the pair name using the actual expiry date, which
is contained in the exchanges "contract_code".

Here's what you get for BTC querying https://www.hbdm.com/api/v1/contract_contract_info on 2019 Aug 16:
[{"symbol":"BTC","contract_code":"BTC190816","contract_type":"this_week","contract_size":100.000000000000000000,"price_tick":0.010000000000000000,"delivery_date":"20190816","create_date":"20190802","contract_status":1}
,{"symbol":"BTC","contract_code":"BTC190823","contract_type":"next_week","contract_size":100.000000000000000000,"price_tick":0.010000000000000000,"delivery_date":"20190823","create_date":"20190809","contract_status":1}
,{"symbol":"BTC","contract_code":"BTC190927","contract_type":"quarter","contract_size":100.000000000000000000,"price_tick":0.010000000000000000,"delivery_date":"20190927","create_date":"20190614","contract_status":1},
...]
So we return BTC190927 as the pair name for the BTC quarterly future.

'''
from collections import defaultdict
import logging
from typing import Dict, Tuple
import zlib
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, FUNDING, HUOBI_DM, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize


LOG = logging.getLogger('feedhandler')


class HuobiDM(Feed):
    id = HUOBI_DM
    symbol_endpoint = 'https://www.hbdm.com/api/v1/contract_contract_info'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        """
        Mapping is, for instance: {"BTC_CW":"BTC190816"}
        See header comments in this file
        """
        mapping = {
            "this_week": "CW",
            "next_week": "NW",
            "quarter": "CQ",
            "next_quarter": "NQ"
        }
        symbols = {}
        info = defaultdict(dict)

        for e in data['data']:
            symbols[f"{e['symbol']}_{mapping[e['contract_type']]}"] = e['contract_code']
            info['tick_size'][e['contract_code']] = e['price_tick']
            info['short_code_mappings'][f"{e['symbol']}_{mapping[e['contract_type']]}"] = e['contract_code']
        return symbols, info

    def __init__(self, **kwargs):
        super().__init__('wss://www.hbdm.com/ws', **kwargs)

    def __reset(self):
        self.l2_book = {}

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
        pair = self.std_symbol_to_exchange_symbol(msg['ch'].split('.')[1])
        data = msg['tick']
        forced = pair not in self.l2_book

        # When Huobi Delists pairs, empty updates still sent:
        # {'ch': 'market.AKRO-USD.depth.step0', 'ts': 1606951241196, 'tick': {'mrid': 50651100044, 'id': 1606951241, 'ts': 1606951241195, 'version': 1606951241, 'ch': 'market.AKRO-USD.depth.step0'}}
        # {'ch': 'market.AKRO-USD.depth.step0', 'ts': 1606951242297, 'tick': {'mrid': 50651100044, 'id': 1606951242, 'ts': 1606951242295, 'version': 1606951242, 'ch': 'market.AKRO-USD.depth.step0'}}
        if 'bids' in data and 'asks' in data:
            update = {
                BID: sd({
                    Decimal(price): Decimal(amount)
                    for price, amount in data['bids']
                }),
                ASK: sd({
                    Decimal(price): Decimal(amount)
                    for price, amount in data['asks']
                })
            }

            if not forced:
                self.previous_book[pair] = self.l2_book[pair]
            self.l2_book[pair] = update

            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, False, timestamp_normalize(self.id, msg['ts']), timestamp)

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
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=self.std_symbol_to_exchange_symbol(msg['ch'].split('.')[1]),
                                order_id=trade['id'],
                                side=BUY if trade['direction'] == 'buy' else SELL,
                                amount=Decimal(trade['amount']),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, trade['ts']),
                                receipt_timestamp=timestamp
                                )

    async def message_handler(self, msg: str, conn, timestamp: float):

        # unzip message
        msg = zlib.decompress(msg, 16 + zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
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
        self.__reset()
        client_id = 0
        for chan in self.subscription:
            if chan == FUNDING:
                continue
            for pair in self.subscription[chan]:
                client_id += 1
                pair = self.exchange_symbol_to_std_symbol(pair)
                await conn.write(json.dumps(
                    {
                        "sub": f"market.{pair}.{chan}",
                        "id": str(client_id)
                    }
                ))
