from cryptofeed import FeedHandler
from cryptofeed.exchanges import *
from cryptofeed.backends.quasar import *

async def ticker_info(ticker, receipt_timestamp):
    print(f'Ticker: {ticker} at {receipt_timestamp}')

async def trade_info(trade, receipt_timestamp):
    print(f'Trade: {trade} at {receipt_timestamp}')

async def candle_info(candle, receipt_timestamp):
    print(f'Candle {candle} at {receipt_timestamp}')


def main():
    f = FeedHandler()
    
    f.add_feed(Binance(candle_closed_only=False, channels=[CANDLES], symbols=['BTC-USDT'], callbacks={CANDLES: CandlesQuasar(), CANDLES: candle_info}))
    f.add_feed(Binance(symbols=['BTC-USDT'], channels=[TRADES], callbacks={TRADES: TradeQuasar(), TRADES: trade_info}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerQuasar(), TICKER: ticker_info}))
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: TradeQuasar(), TRADES: trade_info}))

    f.run()

if __name__ == '__main__':
    main()