import asyncio
import cryptofeed
import time
from cryptofeed.exchanges import Binance
from cryptofeed.exchanges.kraken import Kraken

b = Binance()
async def main():
    trades  = await b.trades('BTC-USDT')
    his_trades = await b.trades('BTC-USDT', start=time.time()-60*60*3)
    ticker = await b.ticker('BTC-USDT')
    l2_book = await b.l2_book('BTC-USDT')
    for call in [trades, his_trades, ticker, l2_book]:
        print(call) 
        time.sleep(4)
    
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
