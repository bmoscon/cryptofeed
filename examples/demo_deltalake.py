"""
Copyright (C) 2018-2024 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
"""
from cryptofeed import FeedHandler
from cryptofeed.backends.deltalake import FundingDeltaLake, TickerDeltaLake, TradeDeltaLake
from cryptofeed.defines import FUNDING, TICKER, TRADES
from cryptofeed.exchanges import Binance


def main():
    f = FeedHandler()

    # Define the Delta Lake base path (can be local or S3)
    delta_base_path = 's3://your-bucket/path/to/delta/tables'

    # S3 storage options (remove if using local storage)
    s3_options = {
        "AWS_ACCESS_KEY_ID": "your_access_key",
        "AWS_SECRET_ACCESS_KEY": "your_secret_key",
        "AWS_REGION": "your_region"
    }

    # Common configuration for all callbacks
    common_config = {
        "base_path": delta_base_path,
        "storage_options": s3_options,
        "batch_size": 1000,  # Process in batches of 1000 records
        "flush_interval": 60.0,  # Flush every 60 seconds if batch size not reached
        "optimize_interval": 100000,  # Optimize after 100,000 rows written
        "time_travel": True,
    }

    # Add Binance feed with Delta Lake callbacks
    f.add_feed(Binance(
        channels=[TRADES, FUNDING, TICKER],
        symbols=['BTC-USDT', 'ETH-USDT'],
        callbacks={
            TRADES: TradeDeltaLake(
                **common_config,
                z_order_cols=['timestamp', 'price', 'amount']
            ),
            FUNDING: FundingDeltaLake(
                **common_config,
                z_order_cols=['timestamp', 'rate']
            ),
            TICKER: TickerDeltaLake(
                **common_config,
                partition_cols=['exchange', 'symbol', 'dt'],
                z_order_cols=['timestamp', 'bid', 'ask']
            )
        }
    ))

    f.run()


if __name__ == '__main__':
    main()
