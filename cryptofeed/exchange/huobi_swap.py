import logging
from yapic import json
from decimal import Decimal
import zlib

from sortedcontainers import SortedDict as sd

from cryptofeed.defines import HUOBI_DM, BUY, SELL, TRADES, BID, ASK, L2_BOOK
from cryptofeed.feed import Feed
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std, timestamp_normalize
from cryptofeed.exchange.huobi_dm import HuobiDM


LOG = logging.getLogger('feedhandler')


class HuobiSwap(HuobiDM):
    id = HUOBI_DM

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        Feed.__init__(self, 'wss://api.hbdm.com/swap-ws', pairs=pairs, channels=channels, callbacks=callbacks, config=config, **kwargs)
