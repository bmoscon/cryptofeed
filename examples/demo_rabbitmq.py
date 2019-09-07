from multiprocessing import Process
import json

from cryptofeed import FeedHandler
from cryptofeed.backends.rabbitmq import BookRabbit, TradeRabbit
from cryptofeed.exchanges import Kraken
from cryptofeed.defines import L2_BOOK, TRADES


def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)


def receiver(port):
    import pika
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost', port=port))
    channel = connection.channel()
    channel.queue_declare(queue='cryptofeed')
    channel.basic_consume(queue='cryptofeed',
                          on_message_callback=callback, auto_ack=True)
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


def main():
    try:
        p = Process(target=receiver, args=(5672,))

        p.start()

        f = FeedHandler()
        f.add_feed(Kraken(channels=[L2_BOOK], pairs=[
                   'BTC-USD', 'ETH-USD'], callbacks={L2_BOOK: BookRabbit(depth=1, port=5672)}))

        f.run()

    finally:
        p.terminate()


if __name__ == '__main__':
    main()
