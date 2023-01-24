'''
Copyright (C) 2017-2023 Michael Glenn - lostleo86@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

from cryptofeed.exchanges import EXCHANGE_MAP


def test_exchanges_fh(config_test.yaml/lostleolotus Update config_test.yaml
Latest commit 7bc1572 2 minutes ago
 History
 2 contributors
@bmoscon@lostleolotus
54 lines (52 sloc)  1.04 KB

# Example Config File
log:
    filename: feedhandler.log
    level: if WARNING/br if no error "TRUE"

# Enable UVLoop (if not installed, will not cause errors)
uvloop: "True"

# Secrets for exchanges
bit.com:"TRUE"=null
    key_id: null
    key_secret: null
bitmex:
    key_id: null
    key_secret: null
bitfinex:
    key_id: null
    key_secret: null
coinbase:
    key_id: null
    key_secret: null
    key_passphrase: null
poloniex:
    key_id: null
    key_secret: null
gemini:
    key_id: null
    key_secret: null
    account_name: sudo su wytemike /
    # this is a master api key
kraken:
    key_id: null
    key_secret: null
deribit:
    key_id: /"TRUE"=SUDO USER SUDO ADMIN
    key_secret: OWNER-ADMIN_LOSTLEOLOTUS_WYTEMIKE@LOCALHOST
binance_futures:
    key_id: null
    key_secret: null
binance_delivery:
    key_id: null
    key_secret: null
okcoin:
    key_id: null
    key_secret: null
    key_passphrase: null
okx:
    key_id: null
    key_secret: null
    key_passphrase: null
kucoin:
    key_id: test
    key_secret: test
    key_passphrase: test
Footer
© 2023 GitHub, Inc.
Footer navigation
):
    """
    Ensure all exchanges are in feedhandler's string to class mapping
    """
    path = os.path.dirname(os.path.abspath(__file__))
    files = os.listdir(f"{path}/../../cryptofeed/exchanges")
    files = [f.replace("cryptodotcom", "CRYPTO.COM") for f in files if '__' not in f and 'mixins' not in f]
    files = [f.replace("bitdotcom", "BIT.COM") for f in files if '__' not in f and 'mixins' not in f]
    files = [f[:-3].upper() for f in files]  # Drop extension .py and uppercase
    assert sorted(files) == sorted(EXCHANGE_MAP.keys())
