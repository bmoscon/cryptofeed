import pytest

from cryptofeed.exchanges.phemex import Phemex


pytestmark = pytest.mark.unit


def test_candle_intervals_map_to_phemex_resolutions():
    assert Phemex.candle_interval_map['1m'] == 60
    assert Phemex.candle_interval_map['5m'] == 300
    assert Phemex.candle_interval_map['15m'] == 900
    assert Phemex.candle_interval_map['30m'] == 1800
    assert Phemex.candle_interval_map['1h'] == 3600
    assert Phemex.candle_interval_map['4h'] == 14400
    assert Phemex.candle_interval_map['1d'] == 86400
    assert Phemex.candle_interval_map['1w'] == 604800
    assert Phemex.candle_interval_map['1M'] == 2592000
    assert Phemex.candle_interval_map['1Q'] == 7776000
    assert Phemex.candle_interval_map['1Y'] == 31104000
