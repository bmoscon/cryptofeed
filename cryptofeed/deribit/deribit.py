import logging
import json
import requests

from cryptofeed.feed import Feed
from cryptofeed.defines import DERIBIT, BUY, SELL, TRADES, BID, ASK, TICKER, L2_BOOK
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize

from sortedcontainers import SortedDict as sd
from decimal import Decimal


LOG = logging.getLogger('feedhandler')


class Deribit(Feed):
    id = DERIBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__('wss://www.deribit.com/ws/api/v2', pairs=pairs,
                         channels=channels, config=config, callbacks=callbacks, **kwargs)

        instruments = self.get_instruments()
        if self.config:
            config_instruments = list(self.config.values())
            self.pairs = [
                pair for inner in config_instruments for pair in inner]

        for pair in self.pairs:
            if pair not in instruments:
                raise ValueError(f"{pair} is not active on {self.id}")
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    @staticmethod
    def get_instruments_info():
        r = requests.get(
            'https://www.deribit.com/api/v2/public/getinstruments?expired=false').json()
        return r

    @staticmethod
    def get_instruments():
        r = Deribit.get_instruments_info()
        instruments = [instr['instrumentName'] for instr in r['result']]
        return instruments

    async def _trade(self, msg):
        """
        {
            "params":
            {
                "data":
                [
                    {
                        "trade_seq": 933,
                        "trade_id": "9178",
                        "timestamp": 1550736299753,
                        "tick_direction": 3,
                        "price": 3948.69,
                        "instrument_name": "BTC-PERPETUAL",
                        "index_price": 3930.73,
                        "direction": "sell",
                        "amount": 10
                    }
                ],
                "channel": "trades.BTC-PERPETUAL.raw"
            },
            "method": "subscription",
            "jsonrpc": "2.0"
        }
        """
        for trade in msg["params"]["data"]:
            await self.callbacks[TRADES](
                feed=self.id,
                pair=trade["instrument_name"],
                order_id=trade['trade_id'],
                side=BUY if trade['direction'] == 'buy' else SELL,
                amount=trade['amount'],
                price=trade['price'],
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
            "jsonrpc" : "2.0"}
        '''
        await self.callbacks[TICKER](feed=self.id,
                                     pair=msg["params"]["data"]["instrument_name"],
                                     bid=msg["params"]["data"]['best_bid_price'],
                                     ask=msg["params"]["data"]['best_ask_price'])

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        client_id = 0

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

    async def _book_snapshot(self, msg):
        timestamp = msg["params"]["data"]["timestamp"]
        self.l2_book[msg["params"]["data"]["instrument_name"]] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                # _ is always 'new' for snapshot
                for _, price, amount in msg["params"]["data"]["bids"]
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for _, price, amount in msg["params"]["data"]["asks"]
            })
        }

        await self.book_callback(msg["params"]["data"]["instrument_name"], L2_BOOK, True, None, timestamp_normalize(self.id, timestamp))

    async def _book_update(self, msg):
        timestamp = msg["params"]["data"]["timestamp"]
        delta = {BID: [], ASK: []}

        for action, price, amount in msg["params"]["data"]["bids"]:
            bidask = self.l2_book[msg["params"]
                                  ["data"]["instrument_name"]][BID]
            if action != "delete":
                bidask[price] = Decimal(amount)
                delta[BID].append((Decimal(price), Decimal(amount)))
            else:
                del bidask[price]
                delta[BID].append((Decimal(price), Decimal(amount)))

        for action, price, amount in msg["params"]["data"]["asks"]:
            bidask = self.l2_book[msg["params"]
                                  ["data"]["instrument_name"]][ASK]
            if action != "delete":
                bidask[price] = amount
                delta[ASK].append((Decimal(price), Decimal(amount)))
            else:
                del bidask[price]
                delta[ASK].append((Decimal(price), Decimal(amount)))
        await self.book_callback(msg["params"]["data"]["instrument_name"], L2_BOOK, False, delta, timestamp_normalize(self.id, timestamp))

    async def message_handler(self, msg):
        msg_dict = json.loads(msg)

        # As a first update after subscription, Deribit sends a notification with no data
        if "testnet" in msg_dict.keys():
            LOG.debug("%s: Test response from derbit accepted %s", self.id, msg)
        elif "ticker" == msg_dict["params"]["channel"].split(".")[0]:
            await self._ticker(msg_dict)
        elif "trades" == msg_dict["params"]["channel"].split(".")[0]:
            await self._trade(msg_dict)
        elif "book" == msg_dict["params"]["channel"].split(".")[0]:

            # cheking if we got full book or its update
            # if it's update there is 'prev_change_id' field
            if "prev_change_id" not in msg_dict["params"]["data"].keys():
                await self._book_snapshot(msg_dict)
            elif "prev_change_id" in msg_dict["params"]["data"].keys():
                await self._book_update(msg_dict)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
