'''
Copyright (C) 2018-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from typing import Optional
from cryptofeed import FeedHandler
from cryptofeed.backends.kafka import BookKafka, TradeKafka
from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.exchanges import Coinbase


"""
The AIOKafkaProducer accepts configuration options passed as kwargs to the Kafka callback(s)
either as individual kwargs, an unpacked dictionary `**config_dict`, or both, as in the example below.
The full list of configuration parameters can be found at
https://aiokafka.readthedocs.io/en/stable/api.html#aiokafka.AIOKafkaProducer

You can run a Kafka consumer in the console with the following command
(assuminng the defaults for the consumer group and bootstrap server)

$ kafka-console-consumer --bootstrap-server 127.0.0.1:9092 --topic trades-COINBASE-BTC-USD
"""


class CustomTradeKafka(TradeKafka):
    def topic(self, data: dict) -> str:
        return f"{self.key}-{data['exchange']}"

    def partition_key(self, data: dict) -> Optional[bytes]:
        return f"{data['symbol']}".encode('utf-8')


def main():
    common_kafka_config = {
        'bootstrap_servers': '127.0.0.1:9092',
        'acks': 1,
        'request_timeout_ms': 10000,
        'connections_max_idle_ms': 20000,
    }
    f = FeedHandler({'log': {'filename': 'feedhandler.log', 'level': 'INFO'}})
    cbs = {TRADES: CustomTradeKafka(client_id='Coinbase Trades', **common_kafka_config), L2_BOOK: BookKafka(client_id='Coinbase Book', **common_kafka_config)}

    f.add_feed(Coinbase(max_depth=10, channels=[TRADES, L2_BOOK], symbols=['BTC-USD'], callbacks=cbs))

    f.run()


if __name__ == '__main__':
    main()
