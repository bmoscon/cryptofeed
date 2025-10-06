from __future__ import annotations

import importlib
import sys

import pytest

from cryptofeed.exchanges import get_shim_usage
from cryptofeed.exchanges.shim_monitor import record_shim_use, reset_shim_usage


def test_record_shim_use_logs(caplog):
    reset_shim_usage()
    with caplog.at_level("WARNING", logger="feedhandler"):
        record_shim_use(shim="legacy.module", canonical="cryptofeed.exchanges.ccxt")

    usage = get_shim_usage()
    assert usage["legacy.module"] == 1
    assert any("compat shim import detected" in message for message in caplog.messages)


@pytest.mark.parametrize("module", ["cryptofeed.exchanges.ccxt_generic"])
def test_compatibility_shim_records_usage(module, caplog):
    reset_shim_usage()
    sys.modules.pop(module, None)

    with caplog.at_level("WARNING", logger="feedhandler"):
        importlib.import_module(module)

    usage = get_shim_usage()
    assert usage.get(module, 0) >= 1
    assert any(module in message for message in caplog.messages)

    # Ensure module is available for subsequent imports
    importlib.import_module(module)
