'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

import aiohttp

from cryptofeed import _json as json
from cryptofeed.backends.backend import BackendQueue, PermanentWriteError


LOG = logging.getLogger(__name__)


class HTTPRejected(PermanentWriteError, aiohttp.ClientResponseError):
    pass


def error_message(body: str) -> str:
    try:
        decoded = json.loads(body)
    except Exception:
        return body
    if isinstance(decoded, dict) and isinstance(decoded.get('message'), str):
        return decoded['message']
    return body


class HTTPCallback(BackendQueue):
    retryable_exceptions = (aiohttp.ClientError, TimeoutError)
    RETRYABLE_STATUS = frozenset({408, 429})
    request_timeout = 10.0
    max_salvage = 5
    MAX_BODY = 8192
    MAX_ERROR_BODY = 512

    def __init__(self, addr: str, **kwargs):
        super().__init__(**kwargs)
        self.addr = addr
        self.session = None
        self.headers = None

    async def connect(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.request_timeout))

    async def close(self):
        if self.session is not None and not self.session.closed:
            await self.session.close()
        self.session = None

    def _encode(self, update) -> str:
        raise NotImplementedError

    def _rejected_line(self, body: str, lines: list):
        return None

    def _partial_write(self, body: str, lines: list):
        return None

    async def _post(self, payload: str) -> tuple:
        async with self.session.post(self.addr, data=payload.encode(), headers=self.headers) as resp:
            if resp.status < 400:
                return resp.status, '', None
            body = (await resp.text())[:self.MAX_BODY]
            message = f'{resp.reason}: {body[:self.MAX_ERROR_BODY]}'

            if resp.status >= 500 or resp.status in self.RETRYABLE_STATUS:
                raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status, message=message, headers=resp.headers)
            request_info, history, status, headers = resp.request_info, resp.history, resp.status, resp.headers

            def reject():
                return HTTPRejected(request_info, history, status=status, message=message, headers=headers)

            return status, body, reject

    async def write_batch(self, batch: list):
        if not batch:
            return 0, 0

        await self.connect()
        lines = [line for line in (self._encode(update) for update in batch) if line]
        dropped = len(batch) - len(lines)
        if dropped:
            LOG.warning('%s: %d of %d messages dropped', type(self).__name__, dropped, len(batch))

        written = 0
        for _ in range(self.max_salvage + 1):
            if not lines:
                break

            status, body, reject = await self._post('\n'.join(lines))
            if status < 400:
                written += len(lines)
                break

            discarded = self._partial_write(body, lines)
            if discarded is not None:
                written += len(lines) - discarded
                dropped += discarded
                LOG.error('%s: discarded %d of %d rows - %s', type(self).__name__, discarded, len(lines), body[:self.MAX_ERROR_BODY])
                break

            index = self._rejected_line(body, lines)
            if index is None or not 0 <= index < len(lines):
                raise reject()

            LOG.error('%s: dropping rejected message and retrying %d - %s', type(self).__name__, len(lines) - 1, body[:self.MAX_ERROR_BODY])
            del lines[index]
            dropped += 1
        else:
            raise reject()

        return written, dropped
