'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import zlib
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, HUOBI, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI

    def __init__(self, **kwargs):
        super().__init__('wss://api.huobi.pro/ws', **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _book(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['ch'].split('.')[1])
        data = msg['tick']
        forced = pair not in self.l2_book

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
            'ch': 'market.adausdt.trade.detail',
            'ts': 1597792835344,
            'tick': {
                'id': 101801945127,
                'ts': 1597792835336,
                'data': [
                    {
                        'id': Decimal('10180194512782291967181675'),   <- per docs this is deprecated
                        'ts': 1597792835336,
                        'tradeId': 100341530602,
                        'amount': Decimal('0.1'),
                        'price': Decimal('0.137031'),
                        'direction': 'sell'
                    }
                ]
            }
        }
        """
        for trade in msg['tick']['data']:
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=symbol_exchange_to_std(msg['ch'].split('.')[1]),
                                order_id=trade['tradeId'],
                                side=BUY if trade['direction'] == 'buy' else SELL,
                                amount=Decimal(trade['amount']),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, trade['ts']),
                                receipt_timestamp=timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        # unzip message
        msg = zlib.decompress(msg, 16 + zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        if 'ping' in msg:
            await conn.send(json.dumps({'pong': msg['ping']}))
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
        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                client_id += 1
                await conn.send(json.dumps(
                    {
                        "sub": f"market.{pair}.{chan}",
                        "id": client_id
                    }
                ))
