import logging
import json
from decimal import Decimal
import zlib
import yaml

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import DERIBIT, BUY, SELL, TRADES, BID, ASK, L2_BOOK, TICKER
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Deribit(Feed):
    id = DERIBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__('wss://test.deribit.com/ws/api/v2', pairs=pairs,
                         channels=channels, config=config, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _trade(self, msg):
        """
        {
            "params" : 
            {
                "data" : 
                [
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
                    }
                ],
                "channel" : "trades.BTC-PERPETUAL.raw"
            },
            "method" : "subscription",
            "jsonrpc" : "2.0"
        }
        """
        for trade in msg["params"]["data"]:
            await self.callbacks[TRADES](
                feed=self.id,
                # for PERPETUAL in USD
                pair=pair_exchange_to_std(trade["instrument_name"]),
                order_id=trade['trade_id'],
                side=BUY if trade['direction'] == 'buy' else SELL,
                amount=Decimal(trade['amount']),
                price=Decimal(trade['price']),
                timestamp=timestamp_normalize(self.id, trade['timestamp'])
            )

    async def _ticker(self, msg):
        '''
        {
            "params" : {
                "data" : {
                "timestamp" : 1550652954406,
                "stats" : {
                    "volume" : null,
                    "low" : null,
                    "high" : null
                },
                "state" : "open",
                "settlement_price" : 3960.14,
                "open_interest" : 0.12759952124659626,
                "min_price" : 3943.21,
                "max_price" : 3982.84,
                "mark_price" : 3940.06,
                "last_price" : 3906,
                "instrument_name" : "BTC-PERPETUAL",
                "index_price" : 3918.51,
                "funding_8h" : 0.01520525,
                "current_funding" : 0.00499954,
                "best_bid_price" : 3914.97,
                "best_bid_amount" : 40,
                "best_ask_price" : 3996.61,
                "best_ask_amount" : 50
                },
                "channel" : "ticker.BTC-PERPETUAL.raw"
            },
            "method" : "subscription",
            "jsonrpc" : "2.0"
        }   
        '''
        await self.callbacks[TICKER](feed=self.id,
                                     pair=pair_exchange_to_std(
                                         msg["params"]["data"]["instrument_name"]),
                                     bid=Decimal(
                                         msg["params"]["data"]['best_bid_price']),
                                     ask=Decimal(msg["params"]["data"]['best_ask_price']))

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        client_id = 0

        # test data
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

    async def message_handler(self, msg):
        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        msg_dict = yaml.load(msg)

        # As a first update after subscription, Deribit sends a notification with no data
        if "testnet" in msg_dict.keys():
            LOG.warning(
                "%s: Test response from derbit accepted %s", self.id, msg)
        elif "ticker" == msg_dict["params"]["channel"].split(".")[0]:
            await self._ticker(msg_dict)
        elif "trades" == msg_dict["params"]["channel"].split(".")[0]:
            await self._trade(msg_dict)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)