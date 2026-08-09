'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest

from cryptofeed.callback import Callback, ExecutorCallback
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


def sync_cb(obj, ts):
    pass


async def async_cb(obj, ts):
    pass


def test_callback_rejects_sync():
    with pytest.raises(TypeError, match='ExecutorCallback'):
        Callback(sync_cb)


def test_callback_accepts_async_and_none():
    Callback(async_cb)
    Callback(None)


async def test_executor_callback_dispatches():
    calls = []
    cb = ExecutorCallback(lambda obj, ts: calls.append((obj, ts)))
    await cb('trade', 1.0)
    assert calls == [('trade', 1.0)]


def test_executor_callback_rejects_async():
    with pytest.raises(TypeError):
        ExecutorCallback(async_cb)


def test_feed_rejects_sync_callback():
    # exercises the real Feed path offline
    with pytest.raises(TypeError, match='ExecutorCallback'):
        Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: sync_cb}, config={'log': {'disabled': True}})


def test_feed_accepts_executor_wrapped_callback():
    Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: ExecutorCallback(sync_cb)}, config={'log': {'disabled': True}})
