'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''


class MissingSequenceNumber(Exception):
    pass


class MissingMessage(Exception):
    pass


class UnsupportedSymbol(Exception):
    pass


class UnsupportedDataFeed(Exception):
    pass


class UnsupportedTradingOption(Exception):
    pass


class UnsupportedType(Exception):
    pass


class ExhaustedRetries(Exception):
    pass


class BidAskOverlapping(Exception):
    pass


class BadChecksum(Exception):
    pass


class RestResponseError(Exception):
    pass
