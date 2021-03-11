"""
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
"""
import logging
import zlib
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Union, Tuple

from sortedcontainers import SortedDict as sd
from collections import deque
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, HUOBI, L2_BOOK, SELL, TRADES, TICKER
from cryptofeed.feed import Feed
from cryptofeed.standards import (
    symbol_exchange_to_std,
    symbol_std_to_exchange,
    timestamp_normalize,
)


LOG = logging.getLogger("feedhandler")


class Huobi(Feed):
    id = HUOBI
    valid_depths = [5, 20]  # 150 version not same as 5 and 20

    def __init__(self, **kwargs):
        super().__init__({}, **kwargs)
        self.ws_endpoint = "wss://api.huobi.pro"
        self.address = self._address()
        self.l2_cache = deque(maxlen=512)
        self.last_prev_seq_num = {}
        self.already_req = {}
        self._reset()

    def _address(self):
        ret = {}
        for chan in self.channels if not self.subscription else self.subscription:
            if "mbp" in chan:
                ret[chan] = self.ws_endpoint + "/feed"
            else:
                ret[chan] = self.ws_endpoint + "/ws"
        return ret

    def _reset(self):
        self.forced = defaultdict(bool)
        self.l2_book = {}
        self.prev_seq_num = {}
        self.already_req = {}

    async def _send_mbp_req(self, conn: AsyncConnection, pair: str):
        max_depth = self.max_depth if self.max_depth else 20
        if max_depth not in self.valid_depths:
            for d in self.valid_depths:
                if d > max_depth:
                    max_depth = d

        self.client_id += 1
        await conn.send(
            json.dumps({"req": f"market.{pair}.mbp.{max_depth}", "id": self.client_id})
        )

    async def _mbp_req(self, conn: AsyncConnection, msg: dict, pair: str, timestamp):
        """
        Req request json:
        {
            "req": "market.btcusdt.mbp.5",
            "id": "id2"
        }
        """
        """
        Req response json:
        {
            "id": "id2",
            "rep": "market.btcusdt.mbp.150",
            "status": "ok",
            "data": {
                "seqNum": 100020142010,
                "bids": [
                    [618.37, 71.594], // [price, size]
                    [423.33, 77.726],
                    [223.18, 47.997],
                    [219.34, 24.82],
                    [210.34, 94.463]
            ],
                "asks": [
                    [650.59, 14.909733438479636],
                    [650.63, 97.996],
                    [650.77, 97.465],
                    [651.23, 83.973],
                    [651.42, 34.465]
                ]
            }
        }
        """
        exchange_pair = pair
        pair = symbol_exchange_to_std(exchange_pair)
        # response already received, so reset the request limit
        self.already_req[pair] = False
        self.last_prev_seq_num[pair] = msg["data"]["seqNum"]

        tmp = []
        for k, v in self.l2_cache:
            if k == pair and v["tick"]["prevSeqNum"] >= self.last_prev_seq_num[pair]:
                tmp.append(v)

        self.l2_book[pair] = {BID: sd(), ASK: sd()}
        for s, side in (("bids", BID), ("asks", ASK)):
            for update in msg["data"][s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])
                self.l2_book[pair][side][price] = amount

        # update orderbook from cache
        delta = {BID: [], ASK: []}
        for msg in tmp:
            ts = msg["ts"]

            if "bids" in msg["tick"]:
                side = BID
                for update in msg["tick"]["bids"]:
                    price = Decimal(update[0])
                    amount = Decimal(update[1])

                    if amount == 0:
                        if price in self.l2_book[pair][side]:
                            del self.l2_book[pair][side][price]
                            delta[side].append((price, amount))
                    else:
                        self.l2_book[pair][side][price] = amount
                        delta[side].append((price, amount))

            if "asks" in msg["tick"]:
                side = ASK
                for update in msg["tick"]["asks"]:
                    price = Decimal(update[0])
                    amount = Decimal(update[1])

                    if amount == 0:
                        if price in self.l2_book[pair][side]:
                            del self.l2_book[pair][side][price]
                            delta[side].append((price, amount))
                    else:
                        self.l2_book[pair][side][price] = amount
                        delta[side].append((price, amount))
            self.last_prev_seq_num[pair] = msg["tick"]["seqNum"]

        skip_update, forced = self._check_update_id(pair, msg)
        if skip_update:
            return

        await self.book_callback(
            self.l2_book[pair],
            L2_BOOK,
            pair,
            forced,
            delta,
            timestamp_normalize(self.id, ts),
            timestamp,
        )

    def _check_update_id(self, pair: str, msg: dict) -> Tuple[bool, bool]:
        skip_update = False
        forced = not self.forced[pair]

        if "rep" in msg:
            tick = msg["data"]
        else:
            tick = msg["tick"]

        if forced and tick["seqNum"] <= self.last_prev_seq_num[pair]:
            skip_update = True
        elif (
            forced
            and tick["prevSeqNum"] <= self.last_prev_seq_num[pair] <= tick["seqNum"]
        ):
            self.last_prev_seq_num[pair] = tick["seqNum"]
            self.forced[pair] = True
        elif not forced and self.last_prev_seq_num[pair] == tick["prevSeqNum"]:
            self.last_prev_seq_num[pair] = tick["seqNum"]
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            skip_update = True

        return skip_update, forced

    async def _book(
        self, conn: AsyncConnection, msg: dict, pair: str, timestamp: float
    ):
        """
        Incremental Update json:
        {
            "ch": "market.btcusdt.mbp.5",
            "ts": 1573199608679, //system update time
            "tick": {
                    "seqNum": 100020146795,
                        "prevSeqNum": 100020146794,
                    "asks": [
                            [645.140000000000000000, 26.755973959140651643] // [price, size]
                    ]
                }
        }
        """
        exchange_pair = pair
        pair = symbol_exchange_to_std(exchange_pair)

        if pair not in self.l2_book:
            self.l2_cache.append((pair, msg))

            if pair not in self.already_req:
                await self._send_mbp_req(conn, exchange_pair)
                self.already_req[pair] = True
            elif self.already_req[pair] != True:
                await self._send_mbp_req(conn, exchange_pair)
                self.already_req[pair] = True
            return

        skip_update, forced = self._check_update_id(pair, msg)
        if skip_update:
            return

        delta = {BID: [], ASK: []}
        ts = msg["ts"]

        if "bids" in msg["tick"]:
            side = BID
            for update in msg["tick"]["bids"]:
                price = Decimal(update[0])
                amount = Decimal(update[1])

                if amount == 0:
                    if price in self.l2_book[pair][side]:
                        del self.l2_book[pair][side][price]
                        delta[side].append((price, amount))
                else:
                    self.l2_book[pair][side][price] = amount
                    delta[side].append((price, amount))
        elif "asks" in msg["tick"]:
            side = ASK
            for update in msg["tick"]["asks"]:
                price = Decimal(update[0])
                amount = Decimal(update[1])

                if amount == 0:
                    if price in self.l2_book[pair][side]:
                        del self.l2_book[pair][side][price]
                        delta[side].append((price, amount))
                else:
                    self.l2_book[pair][side][price] = amount
                    delta[side].append((price, amount))
        else:
            LOG.warning("%s: Unexpected mbp message received: %s", self.id, msg)

        await self.book_callback(
            self.l2_book[pair],
            L2_BOOK,
            pair,
            forced,
            delta,
            timestamp_normalize(self.id, ts),
            timestamp,
        )

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
        for trade in msg["tick"]["data"]:
            await self.callback(
                TRADES,
                feed=self.id,
                symbol=symbol_exchange_to_std(msg["ch"].split(".")[1]),
                order_id=trade["tradeId"],
                side=BUY if trade["direction"] == "buy" else SELL,
                amount=Decimal(trade["amount"]),
                price=Decimal(trade["price"]),
                timestamp=timestamp_normalize(self.id, trade["ts"]),
                receipt_timestamp=timestamp,
            )

    async def _ticker(self, msg: dict, timestamp: float):
        """
        Huobi called Ticker as BBO
        {
            "ch": "market.btcusdt.bbo",
            "ts": 1489474082831, //system update time
            "tick": {
                "symbol": "btcusdt",
                "quoteTime": "1489474082811",
                "bid": "10008.31",
                "bidSize": "0.01",
                "ask": "10009.54",
                "askSize": "0.3",
                "seqId":"10242474683"
            }
        }
        """
        pair = symbol_exchange_to_std(msg["ch"].split(".")[1])
        bid = Decimal(msg["tick"]["bid"])
        ask = Decimal(msg["tick"]["ask"])
        ts = timestamp_normalize(self.id, msg["ts"])

        await self.callback(
            TICKER,
            feed=self.id,
            symbol=pair,
            bid=bid,
            ask=ask,
            timestamp=ts,
            receipt_timestamp=timestamp,
        )

    async def message_handler(self, msg: str, conn, timestamp: float):

        # unzip message
        msg = zlib.decompress(msg, 16 + zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        if "ping" in msg:
            await conn.send(json.dumps({"pong": msg["ping"]}))
        elif "status" in msg and msg["status"] == "ok":
            if "data" in msg and "seqNum" in msg["data"]:
                await self._mbp_req(conn, msg, msg["rep"].split(".")[1], timestamp)
            return
        elif "ch" in msg:
            if "trade" in msg["ch"]:
                await self._trade(msg, timestamp)
            elif "bbo" in msg["ch"]:
                await self._ticker(msg, timestamp)
            elif "depth" or "mbp" in msg["ch"]:
                await self._book(conn, msg, msg["ch"].split(".")[1], timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self._reset()
        self.client_id = 0
        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                self.client_id += 1
                await conn.send(
                    json.dumps({"sub": f"market.{pair}.{chan}", "id": self.client_id})
                )
