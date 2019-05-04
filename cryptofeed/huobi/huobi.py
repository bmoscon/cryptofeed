'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import json
from decimal import Decimal
import zlib

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import HUOBI, BUY, SELL, TRADES, BID, ASK, L2_BOOK
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__('wss://api.huobi.pro/ws', pairs=pairs, channels=channels, config=config, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _book(self, msg):
        pair = pair_exchange_to_std(msg['ch'].split('.')[1])
        data = msg['tick']
        self.l2_book[pair] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                for price, amount in data['bids']
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for price, amount in data['asks']
            })
        }

        await self.book_callback(pair, L2_BOOK, False, False, timestamp_normalize(self.id, msg['ts']))

    async def _trade(self, msg):
        """
        {
            'ch': 'market.btcusd.trade.detail',
            'ts': 1549773923965,
            'tick': {
                'id': 100065340982,
                'ts': 1549757127140,
                'data': [{'id': '10006534098224147003732', 'amount': Decimal('0.0777'), 'price': Decimal('3669.69'), 'direction': 'buy', 'ts': 1549757127140}]}}
        """
        for trade in msg['tick']['data']:
            await self.callbacks[TRADES](
                feed=self.id,
                pair=pair_exchange_to_std(msg['ch'].split('.')[1]),
                order_id=trade['id'],
                side=BUY if trade['direction'] == 'buy' else SELL,
                amount=Decimal(trade['amount']),
                price=Decimal(trade['price']),
                timestamp=timestamp_normalize(self.id, trade['ts'])
            )

    async def message_handler(self, msg):
        # unzip message
        msg = zlib.decompress(msg, 16+zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        if 'ping' in msg:
            await self.websocket.send(json.dumps({'pong': msg['ping']}))
        elif 'status' in msg and msg['status'] == 'ok':
            return
        elif 'ch' in msg:
            if 'trade' in msg['ch']:
                await self._trade(msg)
            elif 'depth' in msg['ch']:
                await self._book(msg)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        client_id = 0
        for chan in self.channels if self.channels else self.config:
            for pair in self.pairs if self.pairs else self.config[chan]:
                client_id += 1
                await websocket.send(json.dumps(
                    {
                        "sub": f"market.{pair}.{chan}",
                        "id": client_id
                    }
                ))

