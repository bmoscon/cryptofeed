'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

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
    version="1.6.2",
    author="Bryant Moscon",
    author_email="bmoscon@gmail.com",
    description="Cryptocurrency Exchange Websocket Data Feed Handler",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    license="XFree86",
    keywords=["cryptocurrency", "bitcoin", "btc", "feed handler", "market feed", "market data",
              "Bitcoin.com", "Bitfinex", "BitMax", "Bitstamp", "Bittrex", "Blockchain.com", "Bybit",
              "Binance", "BitMEX", "CoinBene", "Coinbase", "Deribit", "EXX", "FTX", "Gemini",
              "HitBTC", "Huobi", "Kraken", "OKCoin", "OKEx", "Poloniex", "Upbit"],
    url="https://github.com/bmoscon/cryptofeed",
    packages=find_packages(exclude=['tests*']),
    package_data={'': ['rest/config.yaml']},
    cmdclass={'test': Test},
    python_requires='>=3.7',
    classifiers=[
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Framework :: AsyncIO",
    ],
    tests_require=["pytest", "pyyaml"],
    install_requires=[
        "requests>=2.18.4",
        "websockets>=7.0",
        "sortedcontainers>=1.5.9",
        "pandas",
        "aiohttp>=3.7.1",
        "aiofile>=2.0.0",
        "yapic.json>=1.4.3",
        # Two (optional) dependencies that speed up Cryptofeed:
        "aiodns>=1.1",  # aiodns speeds up DNS resolving
        "cchardet",     # cchardet is a faster replacement for chardet
    ],
    extras_require={
        "rest_api": ["pyyaml"],
        "redis": ["aioredis"],
        "arctic": ["arctic"],
        "zmq": ["pyzmq"],
        "mongo": ["motor"],
        "kafka": ["aiokafka"],
        "rabbit": ["aio_pika", "pika"],
        "postgres": ["asyncpg"],
        "all": [
            "pyyaml",
            "aioredis",
            "arctic",
            "pyzmq",
            "motor",
            "aiokafka",
            "aio_pika",
            "pika",
            "asyncpg",
        ],
    },
)
