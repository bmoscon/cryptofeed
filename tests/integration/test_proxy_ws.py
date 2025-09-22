import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from cryptofeed.connection import WSAsyncConn
from cryptofeed.proxy import (
    ProxyConfig,
    ConnectionProxies,
    ProxySettings,
    init_proxy_system,
)


@pytest.mark.asyncio
async def test_ws_conn_uses_socks_proxy(monkeypatch):
    monkeypatch.setitem(sys.modules, 'python_socks', SimpleNamespace())
    settings = ProxySettings(
        enabled=True,
        exchanges={
            'socks': ConnectionProxies(
                websocket=ProxyConfig(url='socks5://proxy.internal:1080')
            )
        }
    )
    init_proxy_system(settings)

    async def fake_connect(*args, **kwargs):
        return AsyncMock()

    with patch('cryptofeed.proxy.websockets.connect', side_effect=fake_connect) as mock_connect:
        conn = WSAsyncConn('wss://example.com/ws', 'socks-test', exchange_id='socks')
        await conn._open()
        assert mock_connect.call_args.kwargs['proxy'] == 'socks5://proxy.internal:1080'
        await conn.close()

    init_proxy_system(ProxySettings(enabled=False))


@pytest.mark.asyncio
async def test_ws_conn_ccxt_default(monkeypatch):
    monkeypatch.setitem(sys.modules, 'python_socks', SimpleNamespace())
    settings = ProxySettings(
        enabled=True,
        default=ConnectionProxies(websocket=ProxyConfig(url='socks5://default-ws:1081')),
        exchanges={
            'backpack': ConnectionProxies(websocket=ProxyConfig(url='socks5://backpack-proxy:1082'))
        }
    )
    init_proxy_system(settings)

    async def fake_connect(*args, **kwargs):
        return AsyncMock()

    with patch('cryptofeed.proxy.websockets.connect', side_effect=fake_connect) as mock_connect:
        conn = WSAsyncConn('wss://ccxt.example/ws', 'ccxt-test', exchange_id='backpack')
        await conn._open()
        assert mock_connect.call_args.kwargs['proxy'] == 'socks5://backpack-proxy:1082'
        await conn.close()

    init_proxy_system(ProxySettings(enabled=False))


@pytest.mark.asyncio
async def test_ws_conn_http_proxy_injects_header(monkeypatch):
    settings = ProxySettings(
        enabled=True,
        exchanges={
            'native': ConnectionProxies(
                websocket=ProxyConfig(url='http://proxy.example.com:8080')
            )
        }
    )
    init_proxy_system(settings)

    async def fake_connect(*args, **kwargs):
        return AsyncMock()

    with patch('cryptofeed.proxy.websockets.connect', side_effect=fake_connect) as mock_connect:
        conn = WSAsyncConn('wss://native.example/ws', 'native-test', exchange_id='native')
        await conn._open()
        headers = mock_connect.call_args.kwargs.get('extra_headers') or mock_connect.call_args.kwargs.get('additional_headers')
        assert headers['Proxy-Connection'] == 'keep-alive'
        assert mock_connect.call_args.kwargs['proxy'] == 'http://proxy.example.com:8080'
        await conn.close()

    init_proxy_system(ProxySettings(enabled=False))


@pytest.mark.asyncio
async def test_ws_conn_missing_python_socks(monkeypatch):
    settings = ProxySettings(
        enabled=True,
        exchanges={
            'socks': ConnectionProxies(
                websocket=ProxyConfig(url='socks5://proxy.internal:1080')
            )
        }
    )
    init_proxy_system(settings)

    monkeypatch.setitem(sys.modules, 'python_socks', None)

    conn = WSAsyncConn('wss://socks.example/ws', 'socks-test', exchange_id='socks')
    with pytest.raises(ImportError):
        await conn._open()

    init_proxy_system(ProxySettings(enabled=False))


@pytest.mark.asyncio
async def test_ws_conn_direct_when_disabled():
    init_proxy_system(ProxySettings(enabled=False))

    async def fake_connect(*args, **kwargs):
        return AsyncMock()

    with patch('cryptofeed.connection.connect', side_effect=fake_connect) as mock_connect:
        conn = WSAsyncConn('wss://direct.example/ws', 'direct-test', exchange_id='native')
        await conn._open()
        assert 'proxy' not in mock_connect.call_args.kwargs
        await conn.close()

    init_proxy_system(ProxySettings(enabled=False))
