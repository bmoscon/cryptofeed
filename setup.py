'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import sys

from setuptools import setup
from setuptools import find_packages
from setuptools.command.test import test as TestCommand


def get_long_description():
    """Read the contents of README.md, INSTALL.md and CHANGES.md files."""
    from os import path

    repo_dir = path.abspath(path.dirname(__file__))
    markdown = []
    for filename in ["README.md", "INSTALL.md", "CHANGES.md"]:
        with open(path.join(repo_dir, filename), encoding="utf-8") as markdown_file:
            markdown.append(markdown_file.read())
    return "\n\n----\n\n".join(markdown)


class Test(TestCommand):
    def run_tests(self):
        import pytest
        errno = pytest.main(['tests/'])
        sys.exit(errno)


setup(
    name="cryptofeed",
    version="1.9.1",
    author="Bryant Moscon",
    author_email="bmoscon@gmail.com",
    description="Cryptocurrency Exchange Websocket Data Feed Handler",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    license="XFree86",
    keywords=["cryptocurrency", "bitcoin", "btc", "feed handler", "market feed", "market data", "crypto assets",
              "Trades", "Tickers", "BBO", "Funding", "Open Interest", "Liquidation", "Order book", "Bid", "Ask",
              "Bitcoin.com", "Bitfinex", "bitFlyer", "BitMax", "Bitstamp", "Bittrex", "Blockchain.com", "Bybit",
              "Binance", "Binance Delivery", "Binance Futures", "Binance US", "BitMEX", "Coinbase", "Deribit", "EXX",
              "FTX", "FTX US", "Gate.io", "Gemini", "HitBTC", "Huobi", "Huobi DM", "Huobi Swap", "Kraken",
              "Kraken Futures", "OKCoin", "OKEx", "Poloniex", "ProBit", "Upbit"],
    url="https://github.com/bmoscon/cryptofeed",
    packages=find_packages(exclude=['tests*']),
    cmdclass={'test': Test},
    python_requires='>=3.7',
    classifiers=[
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Framework :: AsyncIO",
    ],
    tests_require=["pytest"],
    install_requires=[
        "requests>=2.18.4",
        "websockets>=7.0",
        "sortedcontainers>=1.5.9",
        "pandas",
        "pyyaml",
        "aiohttp>=3.7.1, < 4.0.0",
        "aiofile>=2.0.0",
        "yapic.json>=1.6.3",
        'uvloop ; platform_system!="Windows"',
        # Two (optional) dependencies that speed up Cryptofeed:
        "aiodns>=1.1",  # aiodns speeds up DNS resolving
        "cchardet",     # cchardet is a faster replacement for chardet
    ],
    extras_require={
        "arctic": ["arctic"],
        "gcp_pubsub": ["google_cloud_pubsub>=2.4.1", "gcloud_aio_pubsub"],
        "kafka": ["aiokafka>=0.7.0"],
        "mongo": ["motor"],
        "postgres": ["asyncpg"],
        "rabbit": ["aio_pika", "pika"],
        "redis": ["hiredis", "aioredis>=2.0.0a1"],
        "zmq": ["pyzmq"],
        "all": [
            "arctic",
            "google_cloud_pubsub>=2.4.1",
            "gcloud_aio_pubsub"
            "aiokafka>=0.7.0",
            "motor",
            "asyncpg",
            "aio_pika",
            "pika",
            "hiredis",
            "aioredis>=2.0.0a1",
            "pyzmq",
        ],
    },
)
