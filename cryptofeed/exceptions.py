'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''


class MissingSequenceNumber(Exception):
    pass


class UnsupportedSymbol(Exception):
    pass


class UnsupportedDataFeed(Exception):
    pass


class ExhaustedRetries(Exception):
    pass


class BidAskOverlapping(Exception):
    pass


class BadChecksum(Exception):
    pass


class ConnectionClosed(Exception):
    pass
