'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.feedhandler import FeedHandler


__all__ = ['FeedHandler']

logging.getLogger('cryptofeed').addHandler(logging.NullHandler())
