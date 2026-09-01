'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest
from aiohttp import web

from cryptofeed import _json as json
from cryptofeed.backends.backend import BackendCallback, RetryPolicy
from cryptofeed.backends.http import HTTPCallback
from tests.backend.conftest import assert_written, run_backend, samples


pytestmark = pytest.mark.backend

RETRY = RetryPolicy(max_attempts=5, base=0.01, jitter=False)


class TradeHTTP(HTTPCallback, BackendCallback):
    def __init__(self, addr, **kwargs):
        super().__init__(addr, **kwargs)
        self.numeric_type = float
        self.none_to = None

    def _encode(self, update: dict) -> str:
        return json.dumps(update)


@pytest.fixture
async def server():
    posted = []
    failures = {'remaining': 2}

    async def ok(request):
        posted.append(await request.text())
        return web.Response(status=204)

    async def reject(_request):
        return web.Response(status=400, text=json.dumps({'message': 'that is not valid'}))

    async def flaky(request):
        if failures['remaining']:
            failures['remaining'] -= 1
            return web.Response(status=503, text='try again')
        posted.append(await request.text())
        return web.Response(status=204)

    app = web.Application()
    app.router.add_post('/ok', ok)
    app.router.add_post('/reject', reject)
    app.router.add_post('/flaky', flaky)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    try:
        yield f'http://127.0.0.1:{runner.addresses[0][1]}', posted
    finally:
        await runner.cleanup()


async def test_write(server):
    addr, posted = server
    data = samples('trades')
    backend = TradeHTTP(f'{addr}/ok')

    assert_written(await run_backend(backend, data), len(data))
    assert len(posted) == 1, 'the batch should have gone out as a single request'
    assert len(posted[0].splitlines()) == len(data)


async def test_rejection_is_dropped_not_retried(server):
    addr, _posted = server
    data = samples('trades')
    backend = TradeHTTP(f'{addr}/reject', retry=RETRY)

    stats = await run_backend(backend, data)
    assert stats.written == 0
    assert stats.dropped_failed == len(data)
    assert stats.retries == 0
    assert 'that is not valid' in stats.last_error


async def test_server_error_is_retried(server):
    addr, posted = server
    data = samples('trades')
    backend = TradeHTTP(f'{addr}/flaky', retry=RETRY)

    stats = await run_backend(backend, data)
    assert stats.written == len(data)
    assert stats.dropped_failed == 0
    assert stats.retries == 2
    assert len(posted) == 1
