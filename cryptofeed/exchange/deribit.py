from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, DERIBIT, FUNDING, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, SELL, TICKER, TRADES, FILLED
from cryptofeed.feed import Feed
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.standards import timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Deribit(Feed):
    id = DERIBIT
    symbol_endpoint = ['https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&expired=false', 'https://www.deribit.com/api/v2/public/get_instruments?currency=ETH&expired=false']

    @classmethod
    def _parse_symbol_data(cls, data: list, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            for e in entry['result']:
                split = e['instrument_name'].split("-")
                normalized = split[0] + symbol_separator + e['quote_currency'] + "-" + '-'.join(split[1:])
                ret[normalized] = e['instrument_name']
                info['tick_size'][normalized] = e['tick_size']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://www.deribit.com/ws/api/v2', **kwargs)
        self.__reset()

    def __reset(self):
        self.open_interest = {}
        self.l2_book = {}
        self.seq_no = {}

    async def _trade(self, msg: dict, timestamp: float):
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
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=trade["instrument_name"],
                                order_id=trade['trade_id'],
                                side=BUY if trade['direction'] == 'buy' else SELL,
                                amount=Decimal(trade['amount']),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, trade['timestamp']),
                                receipt_timestamp=timestamp,
                                )
            if 'liquidation' in trade:
                await self.callback(LIQUIDATIONS,
                                    feed=self.id,
                                    symbol=trade["instrument_name"],
                                    side=BUY if trade['direction'] == 'buy' else SELL,
                                    leaves_qty=Decimal(trade['amount']),
                                    price=Decimal(trade['price']),
                                    order_id=trade['trade_id'],
                                    status=FILLED,
                                    timestamp=timestamp_normalize(self.id, trade['timestamp']),
                                    receipt_timestamp=timestamp
                                    )

    async def _ticker(self, msg: dict, timestamp: float):
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
        pair = msg['params']['data']['instrument_name']
        ts = timestamp_normalize(self.id, msg['params']['data']['timestamp'])
        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=Decimal(msg["params"]["data"]['best_bid_price']),
                            ask=Decimal(msg["params"]["data"]['best_ask_price']),
                            timestamp=ts,
                            receipt_timestamp=timestamp)

        if "current_funding" in msg["params"]["data"] and "funding_8h" in msg["params"]["data"]:
            await self.callback(FUNDING, feed=self.id,
                                symbol=pair,
                                timestamp=ts,
                                receipt_timestamp=timestamp,
                                rate=msg["params"]["data"]["current_funding"],
                                rate_8h=msg["params"]["data"]["funding_8h"])
        oi = msg['params']['data']['open_interest']
        if pair in self.open_interest and oi == self.open_interest[pair]:
            return
        self.open_interest[pair] = oi
        await self.callback(OPEN_INTEREST,
                            feed=self.id,
                            symbol=pair,
                            open_interest=oi,
                            timestamp=ts,
                            receipt_timestamp=timestamp
                            )

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        client_id = 0
        channels = []
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                channels.append(f"{chan}.{pair}.raw")
        await conn.write(json.dumps(
            {
                "jsonrpc": "2.0",
                "id": client_id,
                "method": "public/subscribe",
                "params": {
                    "channels": channels
                }
            }
        ))

    async def _book_snapshot(self, msg: dict, timestamp: float):
        """
        {
            'jsonrpc': '2.0',
            'method': 'subscription',
            'params': {
                'channel': 'book.BTC-PERPETUAL.raw',
                'data': {
                    'timestamp': 1598232105378,
                    'instrument_name': 'BTC-PERPETUAL',
                    'change_id': 21486665526, '
                    'bids': [['new', Decimal('11618.5'), Decimal('279310.0')], ..... ]
                    'asks': [[ ....... ]]
                }
            }
        }
        """
        ts = msg["params"]["data"]["timestamp"]
        pair = msg["params"]["data"]["instrument_name"]
        self.l2_book[pair] = {
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

        self.seq_no[pair] = msg["params"]["data"]["change_id"]

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp_normalize(self.id, ts), timestamp)

    async def _book_update(self, msg: dict, timestamp: float):
        ts = msg["params"]["data"]["timestamp"]
        pair = msg["params"]["data"]["instrument_name"]

        if msg['params']['data']['prev_change_id'] != self.seq_no[pair]:
            LOG.warning("%s: Missing sequence number detected for %s", self.id, pair)
            LOG.warning("%s: Requesting book snapshot", self.id)
            raise MissingSequenceNumber

        self.seq_no[pair] = msg['params']['data']['change_id']

        delta = {BID: [], ASK: []}

        for action, price, amount in msg["params"]["data"]["bids"]:
            bidask = self.l2_book[pair][BID]
            if action != "delete":
                bidask[price] = Decimal(amount)
                delta[BID].append((Decimal(price), Decimal(amount)))
            else:
                del bidask[price]
                delta[BID].append((Decimal(price), Decimal(amount)))

        for action, price, amount in msg["params"]["data"]["asks"]:
            bidask = self.l2_book[pair][ASK]
            if action != "delete":
                bidask[price] = amount
                delta[ASK].append((Decimal(price), Decimal(amount)))
            else:
                del bidask[price]
                delta[ASK].append((Decimal(price), Decimal(amount)))
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp_normalize(self.id, ts), timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg_dict = json.loads(msg, parse_float=Decimal)

        # As a first update after subscription, Deribit sends a notification with no data
        if "testnet" in msg_dict.keys():
            LOG.debug("%s: Test response from derbit accepted %s", self.id, msg)
        elif "ticker" == msg_dict["params"]["channel"].split(".")[0]:
            await self._ticker(msg_dict, timestamp)
        elif "trades" == msg_dict["params"]["channel"].split(".")[0]:
            await self._trade(msg_dict, timestamp)
        elif "book" == msg_dict["params"]["channel"].split(".")[0]:

            # checking if we got full book or its update
            # if it's update there is 'prev_change_id' field
            if "prev_change_id" not in msg_dict["params"]["data"].keys():
                await self._book_snapshot(msg_dict, timestamp)
            elif "prev_change_id" in msg_dict["params"]["data"].keys():
                await self._book_update(msg_dict, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
