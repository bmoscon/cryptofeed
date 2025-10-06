import logging
from unittest.mock import patch

import pytest

from cryptofeed.connection import HTTPAsyncConn
from cryptofeed.proxy import ProxySettings, init_proxy_system, load_proxy_settings
from tests.util.proxy_assertions import assert_no_credentials, extract_logged_endpoints


@pytest.mark.asyncio
async def test_http_conn_uses_precedence_proxy(proxy_precedence_fixture):
    settings = proxy_precedence_fixture
    conn = HTTPAsyncConn("precedence", exchange_id="binance")
    try:
        await conn._open()
        expected = settings.get_proxy("binance", "http")
        if settings.enabled and expected is not None:
            assert conn.proxy == expected.url
            assert str(conn.conn._default_proxy) == expected.url
        else:
            assert conn.proxy is None
    finally:
        if conn.is_open:
            await conn.close()


@pytest.mark.asyncio
async def test_http_conn_falls_back_to_global(proxy_precedence_fixture):
    settings = proxy_precedence_fixture
    conn = HTTPAsyncConn("fallback", exchange_id="unknown")
    try:
        await conn._open()
        expected = settings.get_proxy("unknown", "http")
        if settings.enabled and expected is not None:
            assert conn.proxy == expected.url
        else:
            assert conn.proxy is None
    finally:
        if conn.is_open:
            await conn.close()


@pytest.mark.asyncio
async def test_http_conn_ccxt_default(proxy_precedence_fixture):
    settings = proxy_precedence_fixture
    conn = HTTPAsyncConn("ccxt", exchange_id="backpack")
    try:
        await conn._open()
        expected = settings.get_proxy("backpack", "http")
        if settings.enabled and expected is not None:
            assert conn.proxy == expected.url
        else:
            # CCXT inherits global defaults if no specific HTTP override
            default_proxy = settings.get_proxy("unknown", "http")
            if settings.enabled and default_proxy is not None:
                assert conn.proxy == default_proxy.url
            else:
                assert conn.proxy is None
    finally:
        if conn.is_open:
            await conn.close()


@pytest.mark.asyncio
async def test_http_conn_direct_when_disabled():
    init_proxy_system(ProxySettings(enabled=False))
    conn = HTTPAsyncConn("direct", exchange_id="binance")
    try:
        await conn._open()
        assert conn.proxy is None
        assert conn.conn._default_proxy is None
    finally:
        if conn.is_open:
            await conn.close()


@pytest.mark.asyncio
async def test_http_proxy_logging_sanitized(monkeypatch):
    monkeypatch.setenv("CRYPTOFEED_PROXY_ENABLED", "true")
    monkeypatch.setenv("CRYPTOFEED_PROXY_DEFAULT__HTTP__URL", "http://user:secret@proxy.example.com:8080")

    settings = load_proxy_settings()
    init_proxy_system(settings)

    logger = logging.getLogger('feedhandler')
    conn = HTTPAsyncConn("logging", exchange_id="binance")
    try:
        with patch.object(logger, 'info') as mock_info:
            await conn._open()
            await conn.close()
        endpoints = extract_logged_endpoints(mock_info.call_args_list)
        assert 'proxy.example.com:8080' in endpoints
        assert_no_credentials([' '.join(map(str, call.args)) for call in mock_info.call_args_list])
    finally:
        init_proxy_system(ProxySettings(enabled=False))
        if conn.is_open:
            await conn.close()
