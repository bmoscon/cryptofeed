from cryptofeed import FeedHandler
from cryptofeed.defines import LIQUIDATIONS
from cryptofeed.exchanges import EXCHANGE_MAP


async def liquidations(data, receipt):
    print(f'Cryptofeed Receipt: {receipt} Exchange: {data.exchange} Symbol: {data.symbol} Side: {data.side} Quantity: {data.quantity} Price: {data.price} ID: {data.id} Status: {data.status}')


def main():
    f = FeedHandler()
    configured = []

    print("Querying exchange metadata")
    for exchange_string, exchange_class in EXCHANGE_MAP.items():
        if LIQUIDATIONS in exchange_class.info()['channels']['websocket']:
            configured.append(exchange_string)
            symbols = [sym for sym in exchange_class.symbols() if 'PINDEX' not in sym]
            f.add_feed(exchange_class(subscription={LIQUIDATIONS: symbols}, callbacks={LIQUIDATIONS: liquidations}))
    print("Starting feedhandler for exchanges:", ', '.join(configured))
    f.run()


if __name__ == '__main__':
    main()
