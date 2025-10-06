"""Compatibility shim for legacy CCXT generic module path."""

from cryptofeed.exchanges.ccxt import generic as _ccxt_generic
from cryptofeed.exchanges.ccxt.builder import *  # noqa: F401,F403
from cryptofeed.exchanges.ccxt.generic import *  # noqa: F401,F403
from cryptofeed.exchanges.shim_monitor import record_shim_use

record_shim_use(
    shim="cryptofeed.exchanges.ccxt_generic",
    canonical="cryptofeed.exchanges.ccxt",
)

_dynamic_import = _ccxt_generic._dynamic_import
