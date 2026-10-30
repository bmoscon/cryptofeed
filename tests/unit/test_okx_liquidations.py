from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cryptofeed import _json as json
from cryptofeed.defines import FILLED, LIQUIDATIONS, SELL
from cryptofeed.exchanges import okx
from cryptofeed.exchanges.okx import OKX


pytestmark = pytest.mark.unit

T = 1793008266666
EMPTY = json.dumps({'code': '0', 'msg': '', 'data': []})


class Stop(Exception):
    pass


def filled(*timestamps):
    # newest first, as OKX returns them
    details = [{'bkLoss': '0', 'bkPx': '80549.3', 'ccy': '', 'posSide': 'long', 'side': 'sell', 'sz': '0.36', 'ts': str(ts)}
               for ts in timestamps]
    return json.dumps({'code': '0', 'msg': '', 'data': [{'details': details, 'instFamily': 'BTC-USDT', 'instType': 'SWAP', 'uly': 'BTC-USDT'}]})


@pytest.fixture
def feed(monkeypatch):
    # Avoid symbol discovery or any live exchange access.
    monkeypatch.setattr(okx, 'asyncio', SimpleNamespace(sleep=AsyncMock()))
    feed = object.__new__(OKX)
    feed._last_liquidation = defaultdict(dict)
    feed.sandbox = False
    feed.exchange_symbol_to_std_symbol = lambda symbol: 'BTC-USDT-PERP'
    feed.callback = AsyncMock()
    feed.http_conn = SimpleNamespace(read=AsyncMock())
    return feed


async def poll(feed, *answers):
    # each answer is one request: filled, then unfilled, once per minute
    feed.http_conn.read.side_effect = list(answers) + [Stop()]
    with pytest.raises(Stop):
        await feed._liquidations(['BTC-USDT-SWAP'])


def emitted(feed):
    calls = [call.args for call in feed.callback.await_args_list]
    assert all(channel == LIQUIDATIONS for channel, _, _ in calls)
    return [(liq.timestamp, liq.side, liq.status) for _, liq, _ in calls]


async def test_liquidations_listed_before_the_start_are_not_emitted(feed):
    await poll(feed, filled(T - 2000, T - 3000), EMPTY, filled(T, T - 1000, T - 2000, T - 3000), EMPTY)

    assert emitted(feed) == [(T / 1000, SELL, FILLED), ((T - 1000) / 1000, SELL, FILLED)]


async def test_poller_restart_does_not_emit_the_same_liquidations_again(feed):
    await poll(feed, filled(T - 1000, T - 2000), EMPTY, filled(T, T - 1000, T - 2000), EMPTY)
    await poll(feed, filled(T, T - 1000, T - 2000), EMPTY)

    assert emitted(feed) == [(T / 1000, SELL, FILLED)]


async def test_first_liquidation_after_an_empty_start_is_emitted(feed):
    await poll(feed, EMPTY, EMPTY, filled(T), EMPTY)

    assert emitted(feed) == [(T / 1000, SELL, FILLED)]
