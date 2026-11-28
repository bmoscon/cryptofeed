import pytest

from cryptofeed.exchanges.kraken_futures import KrakenFutures
from cryptofeed.exchanges.kucoin_futures import KuCoinFutures


pytestmark = pytest.mark.unit


def test_kucoin_futures_renames_only_the_xbt_currency():
    def contract(symbol, base, quote):
        return {'symbol': symbol, 'type': 'FFWCSX', 'status': 'Open', 'baseCurrency': base, 'quoteCurrency': quote,
                'expireDate': None, 'tickSize': 0.1, 'multiplier': 0.001, 'isInverse': False}

    data = {'data': [contract('XBTUSDTM', 'XBT', 'USDT'), contract('AIXBTUSDTM', 'AIXBT', 'USDT')]}

    symbols, _ = KuCoinFutures._parse_symbol_data(data)

    assert symbols == {'BTC-USDT-PERP': 'XBTUSDTM', 'AIXBT-USDT-PERP': 'AIXBTUSDTM'}


def test_kraken_futures_renames_only_the_xbt_currency():
    def instrument(symbol):
        return {'symbol': symbol, 'tradeable': True, 'tickSize': 0.5, 'contractSize': 1}

    data = {'instruments': [instrument('PF_XBTUSD'), instrument('PF_AIXBTUSD'), instrument('FI_XBTUSD_261225')]}

    symbols, _ = KrakenFutures._parse_symbol_data(data)

    assert symbols == {'BTC-USD-PERP': 'PF_XBTUSD', 'AIXBT-USD-PERP': 'PF_AIXBTUSD', 'BTC-USD-26Z25': 'FI_XBTUSD_261225'}
