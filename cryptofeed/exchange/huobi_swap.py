import logging

from cryptofeed.defines import HUOBI_SWAP
from cryptofeed.exchange.huobi_dm import HuobiDM
from cryptofeed.feed import Feed


LOG = logging.getLogger('feedhandler')


class HuobiSwap(HuobiDM):
    id = HUOBI_SWAP

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        Feed.__init__(self, 'wss://api.hbdm.com/swap-ws', pairs=pairs, channels=channels, callbacks=callbacks, config=config, **kwargs)
