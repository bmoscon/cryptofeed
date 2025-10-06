from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from cryptofeed.exchanges.backpack.auth import BackpackAuthHelper, BackpackAuthError
from cryptofeed.exchanges.backpack.config import BackpackConfig, BackpackAuthSettings


PRIVATE_KEY_BYTES = bytes(range(32))
PRIVATE_KEY_B64 = base64.b64encode(PRIVATE_KEY_BYTES).decode()


def config_with_auth() -> BackpackConfig:
    return BackpackConfig(
        enable_private_channels=True,
        auth=BackpackAuthSettings(
            api_key="api",
            public_key=PRIVATE_KEY_B64,
            private_key=PRIVATE_KEY_B64,
        ),
    )


def test_build_auth_headers_returns_expected_signature():
    config = config_with_auth()
    helper = BackpackAuthHelper(config)

    timestamp = 1_700_000_000_123_456
    signature = helper.sign_message(
        timestamp_us=timestamp,
        method="GET",
        path="/api/v1/orders",
        body="",
    )

    # Expected signature computed using libsodium reference implementation
    assert signature == "8jXwyGxIjhZ2OmLkzJ+Zz31gbqbO5LqolJrYKAQ2ppAVeMwpBdVAaYDU/nOxyxFJUm2Zx0zW2ebwhph3VrxzBQ=="


def test_missing_auth_raises_error():
    config = BackpackConfig(enable_private_channels=False)
    with pytest.raises(BackpackAuthError, match="Authentication not enabled"):
        BackpackAuthHelper(config)
