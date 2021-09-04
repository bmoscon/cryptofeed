'''
Copyright (C) 2021-2021  Cryptofeed contributors

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

from cryptofeed import FeedHandler
from cryptofeed.defines import FUNDING, L2_BOOK, OPEN_INTEREST, TRADES
from cryptofeed.exchanges import Bitmex

# ------------------------------------------------------------------------
#
# WARNING: This demo script intentionally fails
#          because the provided API key & secret are wrong (fake)
#          Please create and set your own API key & secret.
#
# ------------------------------------------------------------------------
#
# DO NOT COMMIT YOUR API key & secret IN SOURCE CODE REPOSITORY (GITHUB).
# YOUR CREDENTIALS MAY BE USED BY MALEVOLENT/MALICIOUS/ILL-INTENDED PEOPLE.
#
# ------------------------------------------------------------------------


async def print_all(data, receipt):
    print(data)


# To set API key and secret, you have three options:
#
# 1. Use the environment variables in the following format:
#
#    CF_BITMEX_KEY_ID=XPIRzadE7dQoGoAiIUsRrbJk
#    CF_BITMEX_KEY_SECRET=EJ3sgj1HKM_UfLn0YzQJI9fM2Z2TFwoIyO1v_47dMfiwJoB2
#
# 2. Create a YAML configuration file as the following 'config_example.yml'
#
#    log:
#       filename: demo_bitmex.log
#       level: DEBUG
#    bitmex:
#        key_id: XPIRzadE7dQoGoAiIUsRrbJk
#        key_secret: EJ3sgj1HKM_UfLn0YzQJI9fM2Z2TFwoIyO1v_47dMfiwJoB2
#
# 3. Use a dict as the following example:
config = {
    'log': {
        'filename': 'demo_bitmex.log',
        'level': 'DEBUG'},
    'bitmex': {
        'key_id': 'XPIRzadE7dQoGoAiIUsRrbJk',
        'key_secret': 'EJ3sgj1HKM_UfLn0YzQJI9fM2Z2TFwoIyO1v_47dMfiwJoB2'},
}


def main():

    # if you use the YAML file, pass the filename as the following:
    #
    #    f = FeedHandler(config='path/config_example.yml')
    #
    # in this demo we use the dict:
    f = FeedHandler(config=config)

    bitmex_symbols = Bitmex.info()['symbols']
    f.add_feed(Bitmex(config=config, symbols=bitmex_symbols, channels=[OPEN_INTEREST], callbacks={OPEN_INTEREST: print_all}))
    f.add_feed(Bitmex(config=config, symbols=bitmex_symbols, channels=[TRADES], callbacks={TRADES: print_all}))

    # When using the following no need to pass config when using 'BITMEX'
    f.add_feed('BITMEX', symbols=bitmex_symbols, channels=[FUNDING], callbacks={FUNDING: print_all})
    f.add_feed('BITMEX', symbols=['BTC-USD-PERP'], channels=[L2_BOOK], callbacks={L2_BOOK: print_all})

    f.run()


if __name__ == '__main__':
    main()
