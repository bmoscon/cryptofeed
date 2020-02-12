'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import aiohttp


LOG = logging.getLogger('feedhandler')


class HTTPCallback:
    def __init__(self, addr: str, **kwargs):
        self.addr = addr
        self.session = None

    async def http_write(self, method: str, data, headers=None):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        m = None
        if method.lower() == 'post':
            m = self.session.post
        elif method.lower() == 'put':
            m = self.session.put

        async with m(self.addr, data=data, headers=headers) as resp:
            if resp.status >= 400:
                error = await resp.text()
                LOG.error("%s to %s failed: %d - %s", method.upper(), self.addr, resp.status, error)
            resp.raise_for_status()
