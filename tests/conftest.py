import os
from contextlib import contextmanager
from typing import Iterator

import pytest

from cryptofeed.proxy import (
    ProxyConfig,
    ConnectionProxies,
    ProxySettings,
    init_proxy_system,
    load_proxy_settings,
)

DEFAULT_HTTP = "http://default-proxy:8080"
DEFAULT_WS = "socks5://default-proxy:1081"


def _build_default_settings() -> ProxySettings:
    return ProxySettings(
        enabled=True,
        default=ConnectionProxies(
            http=ProxyConfig(url=DEFAULT_HTTP),
            websocket=ProxyConfig(url=DEFAULT_WS),
        ),
        exchanges={
            "binance": ConnectionProxies(
                http=ProxyConfig(url="http://binance-proxy:8080"),
                websocket=ProxyConfig(url="socks5://binance-proxy:1081"),
            ),
            "backpack": ConnectionProxies(
                websocket=ProxyConfig(url="socks5://backpack-proxy:2080")
            ),
        },
    )


@pytest.fixture(params=["env", "yaml", "programmatic"], scope="function")
def proxy_precedence_fixture(request, monkeypatch, tmp_path) -> Iterator[ProxySettings]:
    """Yield ProxySettings using requested precedence source."""
    settings = _build_default_settings()

    if request.param == "env":
        monkeypatch.setenv("CRYPTOFEED_PROXY_ENABLED", "true")
        monkeypatch.setenv("CRYPTOFEED_PROXY_DEFAULT__HTTP__URL", settings.default.http.url)
        monkeypatch.setenv("CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL", settings.default.websocket.url)
        for exchange, proxies in settings.exchanges.items():
            if proxies.http:
                monkeypatch.setenv(
                    f"CRYPTOFEED_PROXY_EXCHANGES__{exchange.upper()}__HTTP__URL",
                    proxies.http.url,
                )
            if proxies.websocket:
                monkeypatch.setenv(
                    f"CRYPTOFEED_PROXY_EXCHANGES__{exchange.upper()}__WEBSOCKET__URL",
                    proxies.websocket.url,
                )
        resolved = load_proxy_settings()

    elif request.param == "yaml":
        config_yaml = tmp_path / "config.yaml"
        exchanges_block = []
        for exchange, proxies in settings.exchanges.items():
            entries = []
            if proxies.http:
                entries.append(f"      http:\n        url: \"{proxies.http.url}\"\n")
            if proxies.websocket:
                entries.append(f"      websocket:\n        url: \"{proxies.websocket.url}\"\n")
            exchanges_block.append(f"    {exchange}:\n" + "".join(entries))

        config_yaml.write_text(
            "\n".join(
                [
                    "proxy:",
                    "  enabled: true",
                    "  default:",
                    f"    http:\n      url: \"{settings.default.http.url}\"",
                    f"    websocket:\n      url: \"{settings.default.websocket.url}\"",
                    "  exchanges:",
                ]
                + exchanges_block
            )
        )
        monkeypatch.setenv("CRYPTOFEED_CONFIG", str(config_yaml))
        resolved = load_proxy_settings()

    else:  # programmatic
        resolved = settings

    init_proxy_system(resolved)
    yield resolved
    init_proxy_system(ProxySettings(enabled=False))


@pytest.fixture(scope="function")
def proxy_disabled():
    """Ensure proxy system disabled after test."""
    yield
    init_proxy_system(ProxySettings(enabled=False))
