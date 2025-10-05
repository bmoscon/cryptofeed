"""Placeholder integration tests for future CCXT sandbox scenarios."""
from __future__ import annotations

import pytest


@pytest.mark.ccxt_future
@pytest.mark.skip(reason="Sandbox credentials pending; tracked via spec follow-up")
def test_ccxt_private_channels_sandbox_placeholder() -> None:
    """Placeholder for sandbox verification once credentials are available."""


@pytest.mark.ccxt_future
@pytest.mark.skip(reason="Performance profiling deferred to NFR follow-up spec")
def test_ccxt_transport_performance_placeholder() -> None:
    """Placeholder for transport performance regression plan."""
