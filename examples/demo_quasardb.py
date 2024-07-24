from cryptofeed import FeedHandler
from cryptofeed.exchanges import *
from cryptofeed.backends.quasardb import *


async def feed_info(data, receipt_timestamp):
    print(f'{data} recived at {receipt_timestamp}')


def main():
    f = FeedHandler()

    # save to database
    f.add_feed(Binance(channels=[TICKER], symbols=['BTC-USDT'], callbacks={TICKER: TickerQuasar()}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeQuasar()}))
    f.add_feed(Bybit(channels=[CANDLES], symbols=['BTC-USD-PERP'], callbacks={CANDLES: CandlesQuasar()}))
    f.add_feed(Bybit(channels=[OPEN_INTEREST], symbols=['BTC-USD-PERP'], callbacks={OPEN_INTEREST: OpenInterestQuasar()}))
    f.add_feed(Bybit(channels=[INDEX], symbols=['BTC-USD-PERP'], callbacks={INDEX: IndexQuasar()}))
    f.add_feed(Bybit(channels=[LIQUIDATIONS], symbols=['BTC-USD-PERP'], callbacks={LIQUIDATIONS: LiquidationsQuasar()}))

    # print to console
    f.add_feed(Binance(channels=[TICKER], symbols=['BTC-USDT'], callbacks={TICKER: feed_info}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: feed_info}))
    f.add_feed(Bybit(channels=[CANDLES], symbols=['BTC-USD-PERP'], callbacks={CANDLES: feed_info}))
    f.add_feed(Bybit(channels=[OPEN_INTEREST], symbols=['BTC-USD-PERP'], callbacks={OPEN_INTEREST: feed_info}))
    f.add_feed(Bybit(channels=[INDEX], symbols=['BTC-USD-PERP'], callbacks={INDEX: feed_info}))
    f.add_feed(Bybit(channels=[LIQUIDATIONS], symbols=['BTC-USD-PERP'], callbacks={LIQUIDATIONS: feed_info}))

    f.run()


if __name__ == '__main__':
    main()
