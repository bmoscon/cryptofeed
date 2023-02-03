'''
Copyright (C) 2017-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import sys

from setuptools import Extension, setup
from setuptools import find_packages
from setuptools.command.test import test as TestCommand
from Cython.Build import cythonize


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


extra_compile_args = ["/O2" if os.name == "nt" else "-O3"]
define_macros = []

# comment out line to compile with type check assertions
# verify value at runtime with cryptofeed.types.COMPILED_WITH_ASSERTIONS
define_macros.append(('CYTHON_WITHOUT_ASSERTIONS', None))

extension = Extension("cryptofeed.types", ["cryptofeed/types.pyx"],
                      extra_compile_args=extra_compile_args,
                      define_macros=define_macros)

setup(
    name="cryptofeed",
    ext_modules=cythonize([extension], language_level=3, force=True),
    version="2.3.2",
    author="Bryant Moscon",
    author_email="bmoscon@gmail.com",
    description="Cryptocurrency Exchange Websocket Data Feed Handler",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    license="XFree86",
    keywords=["cryptocurrency", "bitcoin", "btc", "feed handler", "market feed", "market data", "crypto assets",
              "Trades", "Tickers", "BBO", "Funding", "Open Interest", "Liquidation", "Order book", "Bid", "Ask",
              "fmfw.io", "Bitfinex", "bitFlyer", "AscendEX", "Bitstamp", "Bittrex", "Blockchain.com", "Bybit",
              "Binance", "Binance Delivery", "Binance Futures", "Binance US", "BitMEX", "Coinbase", "Deribit", "EXX",
              "Gate.io", "Gemini", "HitBTC", "Huobi", "Huobi DM", "Huobi Swap", "Kraken",
              "Kraken Futures", "OKCoin", "OKX", "Poloniex", "ProBit", "Upbit"],
    url="https://github.com/bmoscon/cryptofeed",
    packages=find_packages(exclude=['tests*']),
    cmdclass={'test': Test},
    python_requires='>=3.8',
    classifiers=[
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Framework :: AsyncIO",
    ],
    tests_require=["pytest"],
    install_requires=[
        "requests>=2.18.4",
        "websockets>=10.0",
        "pyyaml",
        "aiohttp==3.8.3",
        "aiofile>=2.0.0",
        "yapic.json>=1.6.3",
        'uvloop ; platform_system!="Windows"',
        # Two (optional) dependencies that speed up Cryptofeed:
        "aiodns>=1.1",  # aiodns speeds up DNS resolving
        "cchardet",  # cchardet is a faster replacement for chardet
        "order_book>=0.6.0"
    ],
    extras_require={
        "arctic": ["arctic", "pandas"],
        "gcp_pubsub": ["google_cloud_pubsub>=2.4.1", "gcloud_aio_pubsub"],
        "kafka": ["aiokafka>=0.7.0"],
        "mongo": ["motor"],
        "postgres": ["asyncpg"],
        "rabbit": ["aio_pika", "pika"],
        "redis": ["hiredis", "aioredis>=2.0.0"],
        "zmq": ["pyzmq"],
        "all": [
            "arctic",
            "google_cloud_pubsub>=2.4.1",
            "gcloud_aio_pubsub",
            "aiokafka>=0.7.0",
            "motor",
            "asyncpg",
            "aio_pika",
            "pika",
            "hiredis",
            "aioredis>=2.0.0",
            "pyzmq",
        ],
    },
)
