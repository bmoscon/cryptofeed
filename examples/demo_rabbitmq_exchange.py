'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from multiprocessing import Process

from cryptofeed import FeedHandler
from cryptofeed.backends.rabbitmq import BookRabbit
from cryptofeed.defines import L2_BOOK
from cryptofeed.exchanges import Kraken


def callback(ch, method, properties, body):
    print(" [x] Received %r" % body.decode())


def receiver(port):
    import pika
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost', port=port))
    channel = connection.channel()
    exchange_name = 'amq.topic'
    exchange_type = 'topic'
    channel.exchange_declare(exchange=exchange_name, exchange_type=exchange_type, durable=True)
    queue_name = 'cryptofeed'
    channel.queue_declare(queue=queue_name)
    channel.queue_bind(exchange=exchange_name, queue=queue_name)
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


def main():
    try:
        p = Process(target=receiver, args=(5672,))

        p.start()

        f = FeedHandler()
        rabbitargs = {'exchange_mode': True, 'exchange_name': 'amq.topic', 'exchange_type': 'topic', 'routing_key': 'cryptofeed', 'passive': False}
        f.add_feed(Kraken(max_depth=2, channels=[L2_BOOK], symbols=['BTC-USD', 'ETH-USD'], callbacks={L2_BOOK: BookRabbit(**rabbitargs)}))

        f.run()

    finally:
        p.terminate()


if __name__ == '__main__':
    main()
