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
from cryptofeed.defines import DERIBIT, BUY, SELL, TRADES, BID, ASK, L2_BOOK
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Deribit(Feed):
    id = DERIBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__('wss://test.deribit.com/ws/api/v2', pairs=pairs, channels=channels, config=config, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}
    """
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
    """
    async def _trade(self, msg):
        """
        {
            "params" : {
            "data" : [
                {
                    "trade_seq" : 933,
                    "trade_id" : "9178",
                    "timestamp" : 1550736299753,
                    "tick_direction" : 3,
                    "price" : 3948.69,
                    "instrument_name" : "BTC-PERPETUAL",
                    "index_price" : 3930.73,
                    "direction" : "sell",
                    "amount" : 10
                },
                {
                    "trade_seq" : 934,
                    "trade_id" : "9179",
                    "timestamp" : 1550736299753,
                    "tick_direction" : 2,
                    "price" : 3946.07,
                    "instrument_name" : "BTC-PERPETUAL",
                    "index_price" : 3930.73,
                    "direction" : "sell",
                    "amount" : 40
                }
                ],
                "channel" : "trades.BTC-PERPETUAL.raw"
            },
            "method" : "subscription",
            "jsonrpc" : "2.0"
        }
        """
        for trade in msg['params']['data']:
            await self.callbacks[TRADES](
                feed=self.id,
                #for PERPETUAL in USD
                pair=pair_exchange_to_std("btcusd"),
                order_id=trade['trade_id'],
                side=BUY if trade['direction'] == 'buy' else SELL,
                amount=Decimal(trade['amount']),
                price=Decimal(trade['price']),
                timestamp=timestamp_normalize(self.id, trade['timestamp'])
            )

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        client_id = 0

        #test data
        #self.pairs = ["BTC-PERPETUAL"]
        #self.channels = ["trades"]
        #

        for chan in self.channels if self.channels else self.config:
            for pair in self.pairs if self.pairs else self.config[chan]:
                client_id += 1
                await websocket.send(json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": client_id,
                        "method": "public/subscribe",
                        "params": {
                            "channels": [
                            f"{chan}.{pair}.raw"
                            ]
                        }
                    }
                ))

