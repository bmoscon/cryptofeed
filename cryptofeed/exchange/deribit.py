import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json
from collections import defaultdict
from datetime import datetime
import requests

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, DERIBIT, FUNDING, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, SELL, TICKER, TRADES, USER_TRADES, PERPETUAL, OPTION, FUTURE, ANY, C, P, BTC, ETH
from cryptofeed.feed import Feed
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.standards import timestamp_normalize, feed_to_exchange, symbol_std_to_exchange, is_authenticated_channel

from cryptofeed.util.instrument import get_instrument_type


LOG = logging.getLogger('feedhandler')

class DeribitInstrument():
    def __init__(self, instrument_name):
        self.instrument_name = instrument_name
        instrument_properties = instrument_name.split('-')
        self.currency = BTC if instrument_properties[0] == 'BTC' else ETH
        if len(instrument_properties) == 2:
            if instrument_properties[1] == 'PERPETUAL':
                self.instrument_type = PERPETUAL
            else:
                self.instrument_type = FUTURE
                self.expiry_date = instrument_properties[1]
        else:
            self.instrument_type = OPTION
            self.expiry_date_str = instrument_properties[1]
            self.expiry_date = datetime.strptime(self.expiry_date_str, "%d%b%y")
            self.expiry_date = self.expiry_date.replace(hour=8)
            self.strike_price = Decimal(instrument_properties[2])
            self.option_type = C if instrument_properties[3] == 'C' else P

class Deribit(Feed):
    id = DERIBIT

    def __init__(self, **kwargs):
        super().__init__('wss://www.deribit.com/ws/api/v2', **kwargs)

        # TODO: the same verification (below) is done in Bitmex => share this code in a common function in super class Feed
        instruments = self.get_instruments()
        pairs = None
        if self.subscription:
            subscribing_instruments = list(self.subscription.values())
            pairs = [pair for inner in subscribing_instruments for pair in inner]

        for pair in set(self.symbols or pairs):
            if Deribit.is_valid_kind(pair):
                continue
            if pair not in instruments:
                raise ValueError(f"{pair} is not active on {self.id}")
        self.__reset()

    def __reset(self):
        self.open_interest = {}
        self.l2_book = {}
        self.seq_no = {}
        self.snapshot = {}

    @staticmethod
    def is_valid_kind(kind):
        return kind in [ANY, FUTURE, OPTION]

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

    @staticmethod
    def get_instrument_objects():
        r = Deribit.get_instruments()
        print(r)
        instruments = [DeribitInstrument(instr) for instr in r]
        return instruments

    @staticmethod
    def build_channel_name(channel, pair):
        if Deribit.is_valid_kind(pair):
            return f"{channel}.{pair}.any.raw"
        return f"{channel}.{pair}.raw"

    async def generate_token(self, conn: AsyncConnection):
        client_id = 0
        await conn.send(json.dumps(
            {
                "jsonrpc": "2.0",
                "id": client_id,
                "method": "public/auth",
                "params": {
                    "grant_type" : "client_credentials",
                    "client_id" : self.key_id,
                    "client_secret" : self.key_secret
                }
            }
        ))

    async def authenticate(self, conn: AsyncConnection):
        if self.requires_authentication:
            await self.generate_token(conn)

    async def subscribe(self, conn: AsyncConnection, reset=True, subscription=None):
        if reset:
            self.__reset()
        if not subscription:
            subscription = self.subscription
        channels = []

        for chan in set(self.channels or subscription):
            for pair in set(self.symbols or subscription[chan]):
                channels.append(Deribit.build_channel_name(chan, pair))
        await self.subscribe_inner(conn, channels)

    async def subscribe_inner(self, conn: AsyncConnection, channels):
        if not channels:
            return
        client_id = 0
        await conn.send(json.dumps(
            {
                "jsonrpc": "2.0",
                "id": client_id,
                "method": "public/subscribe",
                "params": {
                    "channels": channels
                }
            }
        ))

    async def unsubscribe_inner(self, conn: AsyncConnection, channels):
        if not channels:
            return
        client_id = 1
        await conn.send(json.dumps(
            {
                "jsonrpc": "2.0",
                "id": client_id,
                "method": "public/unsubscribe",
                "params": {
                    "channels": channels
                }
            }
        ))

    async def update_subscription(self, subscription=None):
        normalized_subscription = defaultdict(set)
        for channel in subscription:
            chan = feed_to_exchange(self.id, channel)
            if is_authenticated_channel(channel):
                if not self.key_id or not self.key_secret:
                    raise ValueError("Authenticated channel subscribed to, but no auth keys provided")
            normalized_subscription[chan].update([symbol_std_to_exchange(symbol, self.id) for symbol in subscription[channel]])

        channels_to_subscribe = []
        channels_to_unsubscribe = []
        for chan in normalized_subscription:
            for pair in (set(normalized_subscription[chan]) - set(self.subscription[chan])):
                channels_to_subscribe.append(Deribit.build_channel_name(chan, pair))
            for pair in (set(self.subscription[chan]) - set(normalized_subscription[chan])):
                channels_to_unsubscribe.append(Deribit.build_channel_name(chan, pair))
        self.subscription = normalized_subscription
        LOG.info(f"Updating subscription. Channels to subscribe: {channels_to_subscribe}. Channels to unsubscribe: {channels_to_unsubscribe}")
        await self.subscribe_inner(self.connection, channels_to_subscribe)
        await self.unsubscribe_inner(self.connection, channels_to_unsubscribe)

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
            kwargs = {}
            kwargs['trade_seq'] = Decimal(trade['trade_seq'])
            kwargs['mark_price'] = Decimal(trade['mark_price'])
            kwargs['index_price'] = Decimal(trade['index_price'])
            if get_instrument_type(trade["instrument_name"]) == OPTION:
                kwargs['iv'] = Decimal(trade['iv'])
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=trade["instrument_name"],
                                order_id=trade['trade_id'],
                                side=BUY if trade['direction'] == 'buy' else SELL,
                                amount=Decimal(trade['amount']),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, trade['timestamp']),
                                receipt_timestamp=timestamp,
                                **kwargs
                                )
            if 'liquidation' in trade:
                await self.callback(LIQUIDATIONS,
                                    feed=self.id,
                                    symbol=trade["instrument_name"],
                                    side=BUY if trade['direction'] == 'buy' else SELL,
                                    leaves_qty=Decimal(trade['amount']),
                                    price=Decimal(trade['price']),
                                    order_id=trade['trade_id'],
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
        
        bid = Decimal(msg["params"]["data"]["best_bid_price"])
        bid_amount = Decimal(msg["params"]["data"]["best_bid_amount"])
        ask = Decimal(msg["params"]["data"]['best_ask_price'])
        ask_amount = Decimal(msg["params"]["data"]["best_ask_amount"])
        if pair in self.snapshot and self.snapshot[pair] == (bid, bid_amount, ask, ask_amount):
            return
        self.snapshot[pair] = (bid, bid_amount, ask, ask_amount)

        ts = timestamp_normalize(self.id, msg['params']['data']['timestamp'])
        kwargs = {}
        instrument_type = get_instrument_type(pair)
        if instrument_type == OPTION:
            kwargs['bid_iv'] = Decimal(msg["params"]["data"]["bid_iv"])
            kwargs['ask_iv'] = Decimal(msg["params"]["data"]["ask_iv"])
            kwargs['delta'] = Decimal(msg["params"]["data"]["greeks"]["delta"])
            kwargs['gamma'] = Decimal(msg["params"]["data"]["greeks"]["gamma"])
            kwargs['rho'] = Decimal(msg["params"]["data"]["greeks"]["rho"])
            kwargs['theta'] = Decimal(msg["params"]["data"]["greeks"]["theta"])
            kwargs['vega'] = Decimal(msg["params"]["data"]["greeks"]["vega"])
            kwargs['mark_price'] = Decimal(msg["params"]["data"]["mark_price"])
            kwargs['mark_iv'] = Decimal(msg["params"]["data"]["mark_iv"])
            kwargs['underlying_index'] = msg["params"]["data"]["underlying_index"]
            kwargs['underlying_price'] = Decimal(msg["params"]["data"]["underlying_price"])

        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=bid,
                            bid_amount=bid_amount,
                            ask=ask,
                            ask_amount=ask_amount,
                            timestamp=ts,
                            receipt_timestamp=timestamp,
                            **kwargs)

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

    async def _user_trade(self, msg: dict, timestamp: float):
        """
        {
            "params":
            {
                "data":
                [
                    {
                        # "trade_seq" : 30289432,
                        # "trade_id" : "48079254",
                        # "timestamp" : 1590484156350,
                        "tick_direction" : 0,
                        "state" : "filled",
                        "self_trade" : false,
                        "reduce_only" : false,
                        # "price" : 8954,
                        "post_only" : false,
                        "order_type" : "market",
                        # "order_id" : "4008965646",
                        "matching_id" : null,
                        # "mark_price" : 8952.86,
                        "liquidity" : "T",
                        # "instrument_name" : "BTC-PERPETUAL",
                        # "index_price" : 8956.73,
                        "fee_currency" : "BTC",
                        "fee" : 0.00000168,
                        # "direction" : "sell",
                        # "amount" : 20
                    }
                ],
                "channel": "user.trades.BTC-PERPETUAL.raw"
            },
            "method": "subscription",
            "jsonrpc": "2.0"
        }
        """
        for trade in msg["params"]["data"]:
            kwargs = {}
            kwargs['trade_seq'] = Decimal(trade['trade_seq'])
            kwargs['mark_price'] = Decimal(trade['mark_price'])
            kwargs['index_price'] = Decimal(trade['index_price'])
            if get_instrument_type(trade["instrument_name"]) == OPTION:
                kwargs['iv'] = Decimal(trade['iv'])
                kwargs['underlying_price'] = Decimal(trade['underlying_price'])
            await self.callback(USER_TRADES,
                                feed=self.id,
                                symbol=trade["instrument_name"],
                                order_id=trade['trade_id'],
                                side=BUY if trade['direction'] == 'buy' else SELL,
                                amount=Decimal(trade['amount']),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, trade['timestamp']),
                                receipt_timestamp=timestamp,
                                **kwargs
                                )

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg_dict = json.loads(msg, parse_float=Decimal)

        # As a first update after subscription, Deribit sends a notification with no data
        if "result" in msg_dict and "access_token" in msg_dict["result"]:
            LOG.info("%s: Connection successfully authenticated so it is now possible to subscribe to private channels", self.id)
            await self.subscribe(conn, reset=False, subscription=self.authenticated_subscription)
        elif "testnet" in msg_dict:
            LOG.debug("%s: Test response from deribit accepted %s", self.id, msg)
        elif "user" == msg_dict["params"]["channel"].split(".")[0]:
            # info is specifically about the user
            if "trades" == msg_dict["params"]["channel"].split(".")[1]:
                await self._user_trade(msg_dict, timestamp)
        elif "ticker" == msg_dict["params"]["channel"].split(".")[0]:
            await self._ticker(msg_dict, timestamp)
        elif "trades" == msg_dict["params"]["channel"].split(".")[0]:
            await self._trade(msg_dict, timestamp)
        elif "book" == msg_dict["params"]["channel"].split(".")[0]:
            # checking if we got full book or its update
            # if it's update there is 'prev_change_id' field
            if "prev_change_id" not in msg_dict["params"]["data"]:
                await self._book_snapshot(msg_dict, timestamp)
            elif "prev_change_id" in msg_dict["params"]["data"]:
                await self._book_update(msg_dict, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
