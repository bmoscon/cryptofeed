'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.elastic import TradeElastic, FundingElastic, BookDeltaElastic, BookElastic
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase, Bitmex

from cryptofeed.defines import TRADES, FUNDING, L2_BOOK, BOOK_DELTA

"""
after writing, you can query all the trades out with the following curl:
curl -X GET "localhost:9200/book/book/_search" -H 'Content-Type: application/json' -d'
{
    "size": 50,
    "query": {
        "match_all": {}
    }
}
'
"""

def main():
    f = FeedHandler()

    f.add_feed(Coinbase(channels=[L2_BOOK, TRADES], pairs=['BTC-USD'], callbacks={L2_BOOK: BookElastic('http://localhost:9200', numeric_type=float), BOOK_DELTA: BookDeltaElastic('http://localhost:9200', numeric_type=float), TRADES: TradeElastic('http://localhost:9200', numeric_type=float)}))
    f.add_feed(Bitmex(channels=[FUNDING], pairs=['XBTUSD'], callbacks={FUNDING: FundingElastic('http://localhost:9200', numeric_type=float)}))

    f.run()


if __name__ == '__main__':
    main()