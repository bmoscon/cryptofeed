'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import BID, ASK
from cryptofeed.util.book import book_delta


def test_book_delta_simple():
    a = {BID: {
        1.0: 1,
        0.9: 0.5,
        0.8: 2
    },
        ASK: {
            1.1: 1.1,
            1.2: 0.6,
            1.3: 2.1
        }
    }

    b = {BID: {
        0.9: 0.5,
        0.8: 2
    },
        ASK: {
            1.1: 1.1,
            1.2: 0.6,
            1.3: 2.1
        }
    }

    assert book_delta(a, b) == {'bid': [(1.0, 0)], 'ask': []}
    assert book_delta(b, a) == {'bid': [(1.0, 1)], 'ask': []}


def test_book_delta_empty():
    a = {BID: {
        1.0: 1,
        0.9: 0.5,
        0.8: 2
    },
        ASK: {
            1.1: 1.1,
            1.2: 0.6,
            1.3: 2.1
        }
    }
    b = {
        BID: {},
        ASK: {}
    }

    assert book_delta(a, b) == {'bid': [(0.9, 0), (1.0, 0), (0.8, 0)], 'ask': [(1.2, 0), (1.1, 0), (1.3, 0)]}
    assert book_delta(b, a) == {'ask': [(1.2, 0.6), (1.1, 1.1), (1.3, 2.1)], 'bid': [(0.9, 0.5), (1.0, 1), (0.8, 2)]}
