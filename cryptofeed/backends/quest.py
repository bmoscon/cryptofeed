'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.backends.backend import BackendCallback
from cryptofeed.backends.socket import SocketCallback


LOG = logging.getLogger('feedhandler')


class QuestCallback(SocketCallback):
    def __init__(self, host='127.0.0.1', port=9009, key=None, **kwargs):
        super().__init__(f"tcp://{host}", port=port, **kwargs)
        self.key = key if key else self.default_key
        self.numeric_type = float
        self.none_to = None
        self.running = True

    async def writer(self):
        await self.connect()
        while self.running:
            async with self.read_queue() as updates:
                if len(updates) > 0:
                    batch = []
                    for i in range(len(updates)):
                        d = self.format(updates[i])
                        timestamp = updates[i]["timestamp"]
                        timestamp_str = f',timestamp={int(timestamp * 1_000_000_000)}i' if timestamp is not None else ''
                        if 'interval' in updates[i]:
                            trades = f',trades={updates[i]["trades"]},' if updates[i]['trades'] else ','
                            batch.append(f'{self.key}-{updates[i]["exchange"]},symbol={updates[i]["symbol"]},interval={updates[i]["interval"]} start={updates[i]["start"]},stop={updates[i]["stop"]}{trades}open={updates[i]["open"]},close={updates[i]["close"]},high={updates[i]["high"]},low={updates[i]["low"]},volume={updates[i]["volume"]}{timestamp_str},receipt_timestamp={updates[i]["receipt_timestamp"]} {int(updates[i]["receipt_timestamp"] * 1_000_000_000)}')
                        else:
                            batch.append(f'{self.key}-{updates[i]["exchange"]},symbol={updates[i]["symbol"]} {d}{timestamp_str},receipt_timestamp={updates[i]["receipt_timestamp"]} {int(updates[i]["receipt_timestamp"] * 1_000_000_000)}')
                    update = "\n".join(batch) + "\n"
                    self.conn.write(update.encode())

    def format(self, data):
        ret = []
        for key, value in data.items():
            if key in {'timestamp', 'exchange', 'symbol', 'receipt_timestamp'}:
                continue
            if isinstance(value, str):
                ret.append(f'{key}="{value}"')
            else:
                ret.append(f'{key}={value}')
        return ','.join(ret)


class TradeQuest(QuestCallback, BackendCallback):
    default_key = 'trades'

    def format(self, data):
        return f'side="{data["side"]}",price={data["price"]},amount={data["amount"]},id="{str(data["id"])}",type="{str(data["type"])}"'


class FundingQuest(QuestCallback, BackendCallback):
    default_key = 'funding'


class BookQuest(QuestCallback):
    default_key = 'book'


class TickerQuest(QuestCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestQuest(QuestCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsQuest(QuestCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesQuest(QuestCallback, BackendCallback):
    default_key = 'candles'
