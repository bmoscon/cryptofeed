'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import glob

from cryptofeed import FeedHandler
from cryptofeed.defines import TICKER, TRADES, L2_BOOK
from cryptofeed.exchanges import Coinbase, Deribit


async def cb(*args, **kwargs):
    pass


def test_coinbase_playback():
    fh = FeedHandler()
    feed = Coinbase(symbols=['BTC-USD'], callbacks={L2_BOOK: cb, TICKER: cb, TRADES: cb})

    dir = os.path.dirname(os.path.realpath(__file__))
    for pcap in glob.glob(dir + "/../../sample_data/COINBASE*"):
        results = fh.playback(feed, pcap)
        assert results == {'messages_processed': 48642, 'callbacks': {'l2_book': 48251, 'trades': 195, 'ticker': 195}}


def test_deribit_playback():
    fh = FeedHandler()
    feed = Deribit(symbols=['BTC-USD-PERPETUAL', 'ETH-USD-PERPETUAL'], callbacks={L2_BOOK: cb, TRADES: cb})

    dir = os.path.dirname(os.path.realpath(__file__))
    for pcap in glob.glob(dir + "/../../sample_data/DERIBIT*"):
        results = fh.playback(feed, pcap)
        assert results == {'messages_processed': 17913, 'callbacks': {'l2_book': 17871, 'trades': 109}}
