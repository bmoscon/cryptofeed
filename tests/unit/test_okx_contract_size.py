from decimal import Decimal

import pytest

from cryptofeed.exchanges.okx import OKX


pytestmark = pytest.mark.unit


def instrument(inst_type, inst_id, ct_val='', ct_mult='', ct_ccy='', base='', quote=''):
    return {'instType': inst_type, 'instId': inst_id, 'state': 'live', 'baseCcy': base, 'quoteCcy': quote,
            'tickSz': '0.1', 'ctVal': ct_val, 'ctMult': ct_mult, 'ctValCcy': ct_ccy}


def test_contract_size_is_in_symbol_info():
    data = [{'data': [
        instrument('SPOT', 'BTC-USDT', base='BTC', quote='USDT'),
        instrument('SWAP', 'BTC-USDT-SWAP', '0.01', '1', 'BTC'),
        instrument('SWAP', 'BTC-USD-SWAP', '100', '1', 'USD'),
        instrument('FUTURES', 'BTC-USD-261225', '100', '1', 'USD'),
        instrument('OPTION', 'BTC-USD-261030-74000-C', '1', '0.01', 'BTC'),
    ]}]

    symbols, info = OKX._parse_symbol_data(data)

    assert set(symbols) == {'BTC-USDT', 'BTC-USDT-PERP', 'BTC-USD-PERP', 'BTC-USD-26Z25', 'BTC-USD-74000-26V30-call'}
    assert info['contract_size'] == {
        'BTC-USDT-PERP': Decimal('0.01'),
        'BTC-USD-PERP': Decimal('100'),
        'BTC-USD-26Z25': Decimal('100'),
        'BTC-USD-74000-26V30-call': Decimal('0.01'),
    }
    # the currency the size is in the base coin on linear contracts and options, USD on inverse swaps and futures
    assert info['contract_currency'] == {
        'BTC-USDT-PERP': 'BTC',
        'BTC-USD-PERP': 'USD',
        'BTC-USD-26Z25': 'USD',
        'BTC-USD-74000-26V30-call': 'BTC',
    }
