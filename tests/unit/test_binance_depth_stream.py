'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest

from cryptofeed.exchanges import Binance, BinanceDelivery, BinanceFutures


@pytest.mark.parametrize('feed_cls, symbol, interval, stream', [
    (BinanceFutures, 'BTCUSDT', '250ms', 'btcusdt@depth'),
    (BinanceFutures, 'BTCUSDT', '100ms', 'btcusdt@depth@100ms'),
    (BinanceFutures, 'BTCUSDT', '500ms', 'btcusdt@depth@500ms'),
    (BinanceDelivery, 'BTCUSD_PERP', '250ms', 'btcusd_perp@depth'),
    (BinanceDelivery, 'BTCUSD_PERP', '100ms', 'btcusd_perp@depth@100ms'),
    (Binance, 'BTCUSDT', '1000ms', 'btcusdt@depth@1000ms'),
    (Binance, 'BTCUSDT', '100ms', 'btcusdt@depth@100ms'),
])
def test_depth_stream_name(feed_cls, symbol, interval, stream):
    feed = feed_cls(depth_interval=interval)
    feed.subscription = {'depth': [symbol]}
    assert feed._stream_names() == [stream]
