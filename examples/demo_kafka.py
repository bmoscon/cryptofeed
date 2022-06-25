'''
Copyright (C) 2018-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from typing import Optional
from cryptofeed import FeedHandler
from cryptofeed.backends.kafka import BookKafka, TradeKafka
from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.exchanges import Coinbase


"""
You can run a consumer in the console with the following command
(assuminng the defaults for the consumer group and bootstrap server)

$ kafka-console-consumer --bootstrap-server 127.0.0.1:9092 --topic trades-COINBASE-BTC-USD
"""


class CustomTradeKafka(TradeKafka):
    def topic(self, data: dict) -> str:
        return f"{self.key}-{data['exchange']}"

    def partition_key(self, data: dict) -> Optional[bytes]:
        return f"{data['symbol']}".encode('utf-8')


def main():
    f = FeedHandler()
    cbs = {TRADES: CustomTradeKafka(), L2_BOOK: BookKafka()}

    f.add_feed(Coinbase(max_depth=10, channels=[TRADES, L2_BOOK], symbols=['BTC-USD'], callbacks=cbs))

    f.run()


if __name__ == '__main__':
    main()
