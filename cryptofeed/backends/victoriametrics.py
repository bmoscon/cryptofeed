'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.backends.backend import (BackendQueue, BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)
from cryptofeed.backends.socket import SocketCallback

from typing import Optional


LOG = logging.getLogger('feedhandler')


class VictoriaMetricsCallback(SocketCallback):
    def __init__(self, addr: str, port: int, key: Optional[str] = None, **kwargs):
        """
        Parent class for VictoriaMetrics callbacks

        VictoriaMetrics support multiple protocol for data ingestion.
        In the following implementation we present data in InfluxDB Line Protocol format.

        influxDB schema
        ---------------
        MEASUREMENT | TAGS | FIELDS

        Measurement: Data Feed-Exchange (configurable)
        TAGS: symbol
        FIELDS: timestamp, amount, price, other funding specific fields

        InfluxDB Line Protocol to VictoriaMetrics storage
        -------------------------------------------------
        Please note that Field names are mapped to time series names prefixed with
        {measurement}{separator} value, where {separator} equals to _ by default.
        It can be changed with -influxMeasurementFieldSeparator command-line flag.

        For example, the following Influx line:
            foo,tag1=value1,tag2=value2 field1=12,field2=40

        is converted into the following Prometheus data points:
            foo_field1{tag1="value1", tag2="value2"} 12
            foo_field2{tag1="value1", tag2="value2"} 40

        Ref: https://github.com/VictoriaMetrics/VictoriaMetrics#how-to-send-data-from-influxdb-compatible-agents-such-as-telegraf

        Parameters
        ----------
        addr: str
          Address for connection. Should be in the format:
          <protocol>://<address>
          Example:
          tcp://127.0.0.1
          udp://127.0.0.1
         port: int
           port for connection.
         key: str
           key to use when writing data
        """
        super().__init__(addr, port=port, key=key, numeric_type=float, **kwargs)

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        # Convert data to InfluxDB Line Protocol format
        d = ''
        t = ''
        for key, value in data.items():
            if key in {'timestamp', 'feed', 'symbol', 'receipt_timestamp'}:
                continue
            # VictoriaMetrics does not support discrete data as values,
            # convert strings to InfluxDB tags.
            if isinstance(value, str):
                t += f'{key}={value},'
            else:
                d += f'{key}={value},'
        d = d[:-1]
        t = t[:-1]

        update = f'{self.key},feed={feed},symbol={symbol},{t} {d},timestamp={timestamp},receipt_timestamp={receipt_timestamp}\n'
        await self.queue.put(update)


class TradeVictoriaMetrics(VictoriaMetricsCallback, BackendTradeCallback):
    default_key = 'trades'
