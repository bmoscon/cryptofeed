'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.

Shared pieces for the backend layer.
'''
import asyncio
import os
import socket
from decimal import Decimal

import pytest

from cryptofeed.defines import BUY
from cryptofeed.types import Candle, Trade


EXCHANGE = 'TESTEX'
SYMBOL = 'BTC-USD'
PRICE = Decimal('65432.12345678901234')
AMOUNT = Decimal('0.00000001234567')
TIMESTAMP = 1786310525.123456

SERVICES = {
    'redis': ('REDIS_HOST', '127.0.0.1', 6379),
    'postgres': ('POSTGRES_HOST', '127.0.0.1', 5432),
    'questdb': ('QUESTDB_HOST', '127.0.0.1', 9009),
    'mongo': ('MONGO_HOST', '127.0.0.1', 27017),
    'rabbitmq': ('RABBITMQ_HOST', '127.0.0.1', 5672),
    'kafka': ('KAFKA_HOST', '127.0.0.1', 9092),
    'influxdb': ('INFLUXDB_HOST', '127.0.0.1', 8086),
}


def service(name: str) -> tuple:
    env, default_host, port = SERVICES[name]
    return os.environ.get(env, default_host), int(os.environ.get(f'{name.upper()}_PORT', port))


def require(name: str) -> tuple:
    """Return (host, port) for a service, skipping the test if nothing is listening."""
    host, port = service(name)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.5)
        if probe.connect_ex((host, port)) != 0:
            pytest.skip(f'{name} is not reachable at {host}:{port} - see tests/backend/README.md')
    return host, port


def sample_trade(trade_id='1') -> Trade:
    return Trade(EXCHANGE, SYMBOL, BUY, AMOUNT, PRICE, TIMESTAMP, id=trade_id, type='market')


def sample_candle() -> Candle:
    return Candle(EXCHANGE, SYMBOL, TIMESTAMP, TIMESTAMP + 60, '1m', None,
                  PRICE, PRICE, PRICE, PRICE, AMOUNT, True, TIMESTAMP)


async def run_backend(backend, objects, settle: float = 0.4):
    """Start a backend's writer, hand it objects, stop it cleanly - the lifecycle a feed gives it."""
    async with asyncio.TaskGroup() as tg:
        backend.start_writer(tg, name='test.backend')
        for obj in objects:
            await backend(obj, obj.timestamp)
        await asyncio.sleep(settle)
        await backend.stop()


def assert_exact(value, expected: Decimal, field: str):
    """A backend may hand back str, Decimal or float; only the first two can be exact."""
    if isinstance(value, float):
        pytest.fail(f'{field} came back as float ({value!r}) - precision is lost')
    assert Decimal(str(value)) == expected, f'{field} changed in transit: {value!r} != {expected}'
