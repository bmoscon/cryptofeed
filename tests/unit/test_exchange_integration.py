'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

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
    base = os.path.join(path, "../../cryptofeed/exchanges")

    translation = {
        "BIT.COM": "bitdotcom",
        "CRYPTO.COM": "cryptodotcom",
    }

    for exchange in EXCHANGE_MAP.keys():
        module_name = translation.get(exchange, exchange.lower())
        module_path = os.path.join(base, f"{module_name}.py")
        package_path = os.path.join(base, module_name)

        exists = os.path.exists(module_path) or os.path.isdir(package_path)
        assert exists, f"Missing implementation module for {exchange}"
