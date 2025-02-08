'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hmac
import time
from collections import defaultdict
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BALANCES, BID, ASK, BUY, CANDLES, PHEMEX, L2_BOOK, SELL, TRADES, PERPETUAL
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Candle, Balance

LOG = logging.getLogger('feedhandler')


class Phemex(Feed):
    id = PHEMEX
    websocket_endpoints = [WebsocketEndpoint('wss://phemex.com/ws', sandbox='wss://testnet.phemex.com/ws', limit=20)]
    rest_endpoints = [RestEndpoint('https://api.phemex.com', routes=Routes('/exchange/public/cfg/v2/products'))]
    price_scale = {}
    valid_candle_intervals = ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1M', '1Q', '1Y')
    candle_interval_map = {interval: second for interval, second in zip(valid_candle_intervals, [60, 300, 900, 1800, 3600, 14400, 86400, 604800, 2592000, 7776000, 31104000])}

    websocket_channels = {
        BALANCES: 'aop.subscribe',
        L2_BOOK: 'orderbook.subscribe',
        TRADES: 'trade.subscribe',
        CANDLES: 'kline.subscribe',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1_000_000_000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']['products']:
            if entry['status'] != 'Listed':
                continue
            stype = entry['type'].lower()
            if "perpetual" in stype:    # can be "perpetualv2"
                stype = PERPETUAL
            base, quote = entry['displaySymbol'].split("/")
            s = Symbol(base.strip(), quote.strip(), type=stype)
            ret[s.normalized] = entry['symbol']
            info['tick_size'][s.normalized] = entry['tickSize'] if 'tickSize' in entry else entry['quoteTickSize']
            info['instrument_type'][s.normalized] = stype
            # the price scale for spot symbols is not reported via the API but it is documented
            # here in the API docs: https://github.com/phemex/phemex-api-docs/blob/master/Public-Spot-API-en.md#spot-currency-and-symbols
            # the default value for spot is 10^8
            cls.price_scale[s.normalized] = 10 ** entry.get('priceScale', 8)
        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Phemex only allows 5 connections, with 20 subscriptions per connection, check we arent over the limit
        if sum(map(len, self.subscription.values())) > 100:
            raise ValueError(f"{self.id} only allows a maximum of 100 symbol/channel subscriptions")

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

    async def _book(self, msg: dict, timestamp: float):
        """
        {
            'book': {
                'asks': [],
                'bids': [
                    [345475000, 14340]
                ]
            },
            'depth': 30,
            'sequence': 9047872983,
            'symbol': 'BTCUSD',
            'timestamp': 1625329629283990943,
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        ts = self.timestamp_normalize(msg['timestamp'])
        delta = {BID: [], ASK: []}

        if msg['type'] == 'snapshot':
            delta = None
            self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth, bids={Decimal(entry[0]) / Decimal(self.price_scale[symbol]): Decimal(entry[1]) for entry in msg['book']['bids']}, asks={Decimal(entry[0]) / Decimal(self.price_scale[symbol]): Decimal(entry[1]) for entry in msg['book']['asks']})
        else:
            for key, side in (('asks', ASK), ('bids', BID)):
                for price, amount in msg['book'][key]:
                    price = Decimal(price) / Decimal(self.price_scale[symbol])
                    amount = Decimal(amount)
                    delta[side].append((price, amount))
                    if amount == 0:
                        # for some unknown reason deletes can be repeated in book updates
                        if price in self._l2_book[symbol].book[side]:
                            del self._l2_book[symbol].book[side][price]
                    else:
                        self._l2_book[symbol].book[side][price] = amount

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, timestamp=ts, delta=delta)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'sequence': 9047166781,
            'symbol': 'BTCUSD',
            'trades': [
                [1625326381255067545, 'Buy', 345890000, 323]
            ],
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        for ts, side, price, amount in msg['trades']:
            t = Trade(
                self.id,
                symbol,
                BUY if side == 'Buy' else SELL,
                Decimal(amount),
                Decimal(price) / Decimal(self.price_scale[symbol]),
                self.timestamp_normalize(ts),
                raw=msg
            )
            await self.callback(TRADES, t, timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        """
        {
            'kline': [
                [1625332980, 60, 346285000, 346300000, 346390000, 346300000, 346390000, 49917, 144121225]
            ],
            'sequence': 9048385626,
            'symbol': 'BTCUSD',
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])

        for entry in msg['kline']:
            ts, _, _, open, high, low, close, volume, _ = entry
            c = Candle(
                self.id,
                symbol,
                ts,
                ts + self.candle_interval_map[self.candle_interval],
                self.candle_interval,
                None,
                Decimal(open) / Decimal(self.price_scale[symbol]),
                Decimal(close) / Decimal(self.price_scale[symbol]),
                Decimal(high) / Decimal(self.price_scale[symbol]),
                Decimal(low) / Decimal(self.price_scale[symbol]),
                Decimal(volume),
                None,
                None
            )
            await self.callback(CANDLES, c, timestamp)

    async def _user_data(self, msg: dict, timestamp: float):
        '''
        snapshot:

        {
            "accounts":[
                {
                    "accountBalanceEv":100000024,
                    "accountID":675340001,
                    "bonusBalanceEv":0,
                    "currency":"BTC",
                    "totalUsedBalanceEv":1222,
                    "userID":67534
                }
            ],
            "orders":[
                {
                    "accountID":675340001,
                    "action":"New",
                    "actionBy":"ByUser",
                    "actionTimeNs":1573711481897337000,
                    "addedSeq":1110523,
                    "bonusChangedAmountEv":0,
                    "clOrdID":"uuid-1573711480091",
                    "closedPnlEv":0,
                    "closedSize":0,
                    "code":0,
                    "cumQty":2,
                    "cumValueEv":23018,
                    "curAccBalanceEv":100000005,
                    "curAssignedPosBalanceEv":0,
                    "curBonusBalanceEv":0,
                    "curLeverageEr":0,
                    "curPosSide":"Buy",
                    "curPosSize":2,
                    "curPosTerm":1,
                    "curPosValueEv":23018,
                    "curRiskLimitEv":10000000000,
                    "currency":"BTC",
                    "cxlRejReason":0,
                    "displayQty":2,
                    "execFeeEv":-5,
                    "execID":"92301512-7a79-5138-b582-ac185223727d",
                    "execPriceEp":86885000,
                    "execQty":2,
                    "execSeq":1131034,
                    "execStatus":"MakerFill",
                    "execValueEv":23018,
                    "feeRateEr":-25000,
                    "lastLiquidityInd":"AddedLiquidity",
                    "leavesQty":0,
                    "leavesValueEv":0,
                    "message":"No error",
                    "ordStatus":"Filled",
                    "ordType":"Limit",
                    "orderID":"e9a45803-0af8-41b7-9c63-9b7c417715d9",
                    "orderQty":2,
                    "pegOffsetValueEp":0,
                    "priceEp":86885000,
                    "relatedPosTerm":1,
                    "relatedReqNum":2,
                    "side":"Buy",
                    "stopLossEp":0,
                    "stopPxEp":0,
                    "symbol":"BTCUSD",
                    "takeProfitEp":0,
                    "timeInForce":"GoodTillCancel",
                    "tradeType":"Trade",
                    "transactTimeNs":1573712555309040417,
                    "userID":67534
                },
                {
                    "accountID":675340001,
                    "action":"New",
                    "actionBy":"ByUser",
                    "actionTimeNs":1573711490507067000,
                    "addedSeq":1110980,
                    "bonusChangedAmountEv":0,
                    "clOrdID":"uuid-1573711488668",
                    "closedPnlEv":0,
                    "closedSize":0,
                    "code":0,
                    "cumQty":3,
                    "cumValueEv":34530,
                    "curAccBalanceEv":100000013,
                    "curAssignedPosBalanceEv":0,
                    "curBonusBalanceEv":0,
                    "curLeverageEr":0,
                    "curPosSide":"Buy",
                    "curPosSize":5,
                    "curPosTerm":1,
                    "curPosValueEv":57548,
                    "curRiskLimitEv":10000000000,
                    "currency":"BTC",
                    "cxlRejReason":0,
                    "displayQty":3,
                    "execFeeEv":-8,
                    "execID":"80899855-5b95-55aa-b84e-8d1052f19886",
                    "execPriceEp":86880000,
                    "execQty":3,
                    "execSeq":1131408,
                    "execStatus":"MakerFill",
                    "execValueEv":34530,
                    "feeRateEr":-25000,
                    "lastLiquidityInd":"AddedLiquidity",
                    "leavesQty":0,
                    "leavesValueEv":0,
                    "message":"No error",
                    "ordStatus":"Filled",
                    "ordType":"Limit",
                    "orderID":"7e03cd6b-e45e-48d9-8937-8c6628e7a79d",
                    "orderQty":3,
                    "pegOffsetValueEp":0,
                    "priceEp":86880000,
                    "relatedPosTerm":1,
                    "relatedReqNum":3,
                    "side":"Buy",
                    "stopLossEp":0,
                    "stopPxEp":0,
                    "symbol":"BTCUSD",
                    "takeProfitEp":0,
                    "timeInForce":"GoodTillCancel",
                    "tradeType":"Trade",
                    "transactTimeNs":1573712559100655668,
                    "userID":67534
                },
                {
                    "accountID":675340001,
                    "action":"New",
                    "actionBy":"ByUser",
                    "actionTimeNs":1573711499282604000,
                    "addedSeq":1111025,
                    "bonusChangedAmountEv":0,
                    "clOrdID":"uuid-1573711497265",
                    "closedPnlEv":0,
                    "closedSize":0,
                    "code":0,
                    "cumQty":4,
                    "cumValueEv":46048,
                    "curAccBalanceEv":100000024,
                    "curAssignedPosBalanceEv":0,
                    "curBonusBalanceEv":0,
                    "curLeverageEr":0,
                    "curPosSide":"Buy",
                    "curPosSize":9,
                    "curPosTerm":1,
                    "curPosValueEv":103596,
                    "curRiskLimitEv":10000000000,
                    "currency":"BTC",
                    "cxlRejReason":0,
                    "displayQty":4,
                    "execFeeEv":-11,
                    "execID":"0be06645-90b8-5abe-8eb0-dca8e852f82f",
                    "execPriceEp":86865000,
                    "execQty":4,
                    "execSeq":1132422,
                    "execStatus":"MakerFill",
                    "execValueEv":46048,
                    "feeRateEr":-25000,
                    "lastLiquidityInd":"AddedLiquidity",
                    "leavesQty":0,
                    "leavesValueEv":0,
                    "message":"No error",
                    "ordStatus":"Filled",
                    "ordType":"Limit",
                    "orderID":"66753807-9204-443d-acf9-946d15d5bedb",
                    "orderQty":4,
                    "pegOffsetValueEp":0,
                    "priceEp":86865000,
                    "relatedPosTerm":1,
                    "relatedReqNum":4,
                    "side":"Buy",
                    "stopLossEp":0,
                    "stopPxEp":0,
                    "symbol":"BTCUSD",
                    "takeProfitEp":0,
                    "timeInForce":"GoodTillCancel",
                    "tradeType":"Trade",
                    "transactTimeNs":1573712618104628671,
                    "userID":67534
                }
            ],
            "positions":[
                {
                    "accountID":675340001,
                    "assignedPosBalanceEv":0,
                    "avgEntryPriceEp":86875941,
                    "bankruptCommEv":75022,
                    "bankruptPriceEp":90000,
                    "buyLeavesQty":0,
                    "buyLeavesValueEv":0,
                    "buyValueToCostEr":1150750,
                    "createdAtNs":0,
                    "crossSharedBalanceEv":99998802,
                    "cumClosedPnlEv":0,
                    "cumFundingFeeEv":0,
                    "cumTransactFeeEv":-24,
                    "currency":"BTC",
                    "dataVer":4,
                    "deleveragePercentileEr":0,
                    "displayLeverageEr":1000000,
                    "estimatedOrdLossEv":0,
                    "execSeq":1132422,
                    "freeCostEv":0,
                    "freeQty":-9,
                    "initMarginReqEr":1000000,
                    "lastFundingTime":1573703858883133252,
                    "lastTermEndTime":0,
                    "leverageEr":0,
                    "liquidationPriceEp":90000,
                    "maintMarginReqEr":500000,
                    "makerFeeRateEr":0,
                    "markPriceEp":86786292,
                    "orderCostEv":0,
                    "posCostEv":1115,
                    "positionMarginEv":99925002,
                    "positionStatus":"Normal",
                    "riskLimitEv":10000000000,
                    "sellLeavesQty":0,
                    "sellLeavesValueEv":0,
                    "sellValueToCostEr":1149250,
                    "side":"Buy",
                    "size":9,
                    "symbol":"BTCUSD",
                    "takerFeeRateEr":0,
                    "term":1,
                    "transactTimeNs":1573712618104628671,
                    "unrealisedPnlEv":-107,
                    "updatedAtNs":0,
                    "usedBalanceEv":1222,
                    "userID":67534,
                    "valueEv":103596
                }
            ],
            "sequence":1310812,
            "timestamp":1573716998131003833,
            "type":"snapshot"
        }

        incremental update:

        {
            "accounts":[
                {
                    "accountBalanceEv":99999989,
                    "accountID":675340001,
                    "bonusBalanceEv":0,
                    "currency":"BTC",
                    "totalUsedBalanceEv":1803,
                    "userID":67534
                }
            ],
            "orders":[
                {
                    "accountID":675340001,
                    "action":"New",
                    "actionBy":"ByUser",
                    "actionTimeNs":1573717286765750000,
                    "addedSeq":1192303,
                    "bonusChangedAmountEv":0,
                    "clOrdID":"uuid-1573717284329",
                    "closedPnlEv":0,
                    "closedSize":0,
                    "code":0,
                    "cumQty":0,
                    "cumValueEv":0,
                    "curAccBalanceEv":100000024,
                    "curAssignedPosBalanceEv":0,
                    "curBonusBalanceEv":0,
                    "curLeverageEr":0,
                    "curPosSide":"Buy",
                    "curPosSize":9,
                    "curPosTerm":1,
                    "curPosValueEv":103596,
                    "curRiskLimitEv":10000000000,
                    "currency":"BTC",
                    "cxlRejReason":0,
                    "displayQty":4,
                    "execFeeEv":0,
                    "execID":"00000000-0000-0000-0000-000000000000",
                    "execPriceEp":0,
                    "execQty":0,
                    "execSeq":1192303,
                    "execStatus":"New",
                    "execValueEv":0,
                    "feeRateEr":0,
                    "leavesQty":4,
                    "leavesValueEv":46098,
                    "message":"No error",
                    "ordStatus":"New",
                    "ordType":"Limit",
                    "orderID":"e329ae87-ce80-439d-b0cf-ad65272ed44c",
                    "orderQty":4,
                    "pegOffsetValueEp":0,
                    "priceEp":86770000,
                    "relatedPosTerm":1,
                    "relatedReqNum":5,
                    "side":"Buy",
                    "stopLossEp":0,
                    "stopPxEp":0,
                    "symbol":"BTCUSD",
                    "takeProfitEp":0,
                    "timeInForce":"GoodTillCancel",
                    "transactTimeNs":1573717286765896560,
                    "userID":67534
                },
                {
                    "accountID":675340001,
                    "action":"New",
                    "actionBy":"ByUser",
                    "actionTimeNs":1573717286765750000,
                    "addedSeq":1192303,
                    "bonusChangedAmountEv":0,
                    "clOrdID":"uuid-1573717284329",
                    "closedPnlEv":0,
                    "closedSize":0,
                    "code":0,
                    "cumQty":4,
                    "cumValueEv":46098,
                    "curAccBalanceEv":99999989,
                    "curAssignedPosBalanceEv":0,
                    "curBonusBalanceEv":0,
                    "curLeverageEr":0,
                    "curPosSide":"Buy",
                    "curPosSize":13,
                    "curPosTerm":1,
                    "curPosValueEv":149694,
                    "curRiskLimitEv":10000000000,
                    "currency":"BTC",
                    "cxlRejReason":0,
                    "displayQty":4,
                    "execFeeEv":35,
                    "execID":"8d1848a2-5faf-52dd-be71-9fecbc8926be",
                    "execPriceEp":86770000,
                    "execQty":4,
                    "execSeq":1192303,
                    "execStatus":"TakerFill",
                    "execValueEv":46098,
                    "feeRateEr":75000,
                    "lastLiquidityInd":"RemovedLiquidity",
                    "leavesQty":0,
                    "leavesValueEv":0,
                    "message":"No error",
                    "ordStatus":"Filled",
                    "ordType":"Limit",
                    "orderID":"e329ae87-ce80-439d-b0cf-ad65272ed44c",
                    "orderQty":4,
                    "pegOffsetValueEp":0,
                    "priceEp":86770000,
                    "relatedPosTerm":1,
                    "relatedReqNum":5,
                    "side":"Buy",
                    "stopLossEp":0,
                    "stopPxEp":0,
                    "symbol":"BTCUSD",
                    "takeProfitEp":0,
                    "timeInForce":"GoodTillCancel",
                    "tradeType":"Trade",
                    "transactTimeNs":1573717286765896560,
                    "userID":67534
                }
            ],
            "positions":[
                {
                    "accountID":675340001,
                    "assignedPosBalanceEv":0,
                    "avgEntryPriceEp":86843828,
                    "bankruptCommEv":75056,
                    "bankruptPriceEp":130000,
                    "buyLeavesQty":0,
                    "buyLeavesValueEv":0,
                    "buyValueToCostEr":1150750,
                    "createdAtNs":0,
                    "crossSharedBalanceEv":99998186,
                    "cumClosedPnlEv":0,
                    "cumFundingFeeEv":0,
                    "cumTransactFeeEv":11,
                    "currency":"BTC",
                    "dataVer":5,
                    "deleveragePercentileEr":0,
                    "displayLeverageEr":1000000,
                    "estimatedOrdLossEv":0,
                    "execSeq":1192303,
                    "freeCostEv":0,
                    "freeQty":-13,
                    "initMarginReqEr":1000000,
                    "lastFundingTime":1573703858883133252,
                    "lastTermEndTime":0,
                    "leverageEr":0,
                    "liquidationPriceEp":130000,
                    "maintMarginReqEr":500000,
                    "makerFeeRateEr":0,
                    "markPriceEp":86732335,
                    "orderCostEv":0,
                    "posCostEv":1611,
                    "positionMarginEv":99924933,
                    "positionStatus":"Normal",
                    "riskLimitEv":10000000000,
                    "sellLeavesQty":0,
                    "sellLeavesValueEv":0,
                    "sellValueToCostEr":1149250,
                    "side":"Buy",
                    "size":13,
                    "symbol":"BTCUSD",
                    "takerFeeRateEr":0,
                    "term":1,
                    "transactTimeNs":1573717286765896560,
                    "unrealisedPnlEv":-192,
                    "updatedAtNs":0,
                    "usedBalanceEv":1803,
                    "userID":67534,
                    "valueEv":149694
                }
            ],
            "sequence":1315725,
            "timestamp":1573717286767188294,
            "type":"incremental"
        }
        '''
        for entry in msg['accounts']:
            b = Balance(
                self.id,
                entry['currency'],
                Decimal(entry['accountBalanceEv']),
                Decimal(entry['totalUsedBalanceEv']),
                self.timestamp_normalize(msg['timestamp']),
                raw=entry
            )
            await self.callback(BALANCES, b, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'id' in msg and msg['id'] == 100:
            if not msg['error']:
                LOG.info("%s: Auth request result: %s", conn.uuid, msg['result']['status'])
                msg = json.dumps({"id": 101, "method": self.std_channel_to_exchange(BALANCES), "params": []})
                LOG.debug(f"{conn.uuid}: Subscribing to authenticated channels: {msg}")
                await conn.write(msg)
            else:
                LOG.warning("%s: Auth unsuccessful: %s", conn.uuid, msg)
        elif 'id' in msg and msg['id'] == 101:
            if not msg['error']:
                LOG.info("%s: Subscribe to auth channels request result: %s", conn.uuid, msg['result']['status'])
            else:
                LOG.warning(f"{conn.uuid}: Subscription unsuccessful: {msg}")
        elif 'id' in msg and msg['id'] == 1 and not msg['error']:
            pass
        elif 'accounts' in msg:
            await self._user_data(msg, timestamp)
        elif 'book' in msg:
            await self._book(msg, timestamp)
        elif 'trades' in msg:
            await self._trade(msg, timestamp)
        elif 'kline' in msg:
            await self._candle(msg, timestamp)
        elif 'result' in msg:
            if 'error' in msg and msg['error'] is not None:
                LOG.warning("%s: Error from exchange %s", conn.uuid, msg)
                return
            else:
                LOG.warning("%s: Unhandled 'result' message: %s", conn.uuid, msg)
        else:
            LOG.warning("%s: Invalid message type %s", conn.uuid, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset(conn)

        for chan, symbols in conn.subscription.items():
            if not self.exchange_channel_to_std(chan) == BALANCES:
                for sym in symbols:
                    msg = {"id": 1, "method": chan, "params": [sym]}
                    if self.exchange_channel_to_std(chan) == CANDLES:
                        msg['params'] = [*[sym], self.candle_interval_map[self.candle_interval]]
                    LOG.debug(f"{conn.uuid}: Sending subscribe request to public channel: {msg}")
                    await conn.write(json.dumps(msg))

    async def authenticate(self, conn: AsyncConnection):
        if any(self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in self.subscription):
            auth = json.dumps(self._auth(self.key_id, self.key_secret))
            LOG.debug(f"{conn.uuid}: Sending authentication request with message {auth}")
            await conn.write(auth)

    def _auth(self, key_id, key_secret, session_id=100):
        # https://github.com/phemex/phemex-api-docs/blob/master/Public-Contract-API-en.md#api-user-authentication
        expires = int((time.time() + 60))
        signature = str(hmac.new(bytes(key_secret, 'utf-8'), bytes(f'{key_id}{expires}', 'utf-8'), digestmod='sha256').hexdigest())
        auth = {"method": "user.auth", "params": ["API", key_id, signature, expires], "id": session_id}
        return auth
