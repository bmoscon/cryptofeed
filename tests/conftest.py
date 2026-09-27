import sys
import sysconfig

import pytest

from cryptofeed.symbols import Symbols


@pytest.fixture(autouse=True)
def clear_symbols():
    Symbols.clear()
    yield
    Symbols.clear()


def pytest_sessionfinish(session, exitstatus):
    if sysconfig.get_config_var('Py_GIL_DISABLED') and sys._is_gil_enabled():
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        if reporter:
            reporter.write_line('the GIL enabled during run on free-threaded build - an imported package does not declare free-threading support (for aiokafka, set AIOKAFKA_NO_EXTENSIONS=1)', red=True)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
