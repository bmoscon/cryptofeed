from decimal import Decimal
import json

import pika

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class RabbitCallback:
    def __init__(self, host='localhost', port=5672, **kwargs):
        connection = pika.BlockingConnection(pika.ConnectionParameters(host))
        self.con = connection.channel()
        self.con.queue_declare(queue='cryptofeed')


class TradeRabbit(RabbitCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        trade = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                 'side': side, 'amount': float(amount), 'price': float(price)}
        self.con.basic_publish(
            exchange='', routing_key='cryptofeed', body='trades {json.dumps(trade)}')


class FundingRabbit(RabbitCallback):
    async def __call__(self, **kwargs):
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = float(kwargs[key])

        self.con.basic_publish(
            exchange='', routing_key='cryptofeed', body=f'funding {json.dumps(kwargs)}')


class BookRabbit(RabbitCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = kwargs.get('depth', None)
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_convert(book, data, self.depth)
        upd = {'feed': feed, 'pair': pair, 'delta': False, 'data': data}

        if self.depth:
            if upd['data'][BID] == self.previous[BID] and upd['data'][ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = upd['data'][ASK]
            self.previous[BID] = upd['data'][BID]

        self.con.basic_publish(
            exchange='', routing_key='cryptofeed', body=f'book {json.dumps(upd)}')


class BookDeltaRabbit(RabbitCallback):
    async def __call__(self, *, feed, pair, delta, timestamp):
        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_delta_convert(delta, data)
        upd = {'feed': feed, 'pair': pair, 'delta': True, 'data': data}

        self.con.basic_publish(
            exchange='', routing_key='cryptofeed', body=f'book {json.dumps(upd)}')
