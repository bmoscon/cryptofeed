'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

from cryptofeed.exchanges import EXCHANGE_MAP


def test_exchanges_fh():
    """
    Ensure all exchanges are in feedhandler's string to class mapping
    """
    path = os.path.dirname(os.path.abspath(__file__))
    files = os.listdir(f"{path}/../../cryptofeed/exchanges")
    files = [f for f in files if '__' not in f and 'mixins' not in f]
    files = [f[:-3].upper() for f in files]  # Drop extension .py and uppercase
    assert sorted(files) == sorted(EXCHANGE_MAP)
