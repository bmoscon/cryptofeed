'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

import aiohttp

from cryptofeed.backends.backend import BackendQueue


LOG = logging.getLogger('feedhandler')


class HTTPCallback(BackendQueue):
    def __init__(self, addr: str, **kwargs):
        self.addr = addr
        self.session = None

    async def writer(self):
        while True:
            async with self.read_queue() as update:
                await self.http_write(update['data'], headers=update['headers'])

    async def http_write(self, data, headers=None):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        async with self.session.post(self.addr, data=data, headers=headers) as resp:
            if resp.status >= 400:
                error = await resp.text()
                LOG.error("POST to %s failed: %d - %s", self.addr, resp.status, error)
            resp.raise_for_status()
