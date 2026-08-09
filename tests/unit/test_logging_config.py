'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import subprocess
import sys
from logging.handlers import RotatingFileHandler

import pytest

from cryptofeed import FeedHandler
from cryptofeed.log import configure_logging


@pytest.fixture
def clean_logger():
    logger = logging.getLogger('cryptofeed')
    saved_handlers = logger.handlers[:]
    saved_level = logger.level
    saved_propagate = logger.propagate
    for h in logger.handlers[:]:
        if not isinstance(h, logging.NullHandler):
            logger.removeHandler(h)
    logger.propagate = True
    logger.setLevel(logging.NOTSET)
    yield logger
    for h in logger.handlers[:]:
        if h not in saved_handlers:
            h.close()
            logger.removeHandler(h)
    for h in saved_handlers:
        if h not in logger.handlers:
            logger.addHandler(h)
    logger.setLevel(saved_level)
    logger.propagate = saved_propagate


def non_null_handlers(logger):
    return [h for h in logger.handlers if not isinstance(h, logging.NullHandler)]


def test_import_configures_nothing():
    prog = (
        "import logging, cryptofeed\n"
        "h = logging.getLogger('cryptofeed').handlers\n"
        "assert len(h) == 1 and isinstance(h[0], logging.NullHandler), h\n"
        "assert logging.getLogger('cryptofeed').propagate is True\n"
        "assert logging.getLogger().handlers == [], logging.getLogger().handlers\n"
        "print('ok')\n"
    )
    result = subprocess.run([sys.executable, '-c', prog], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'ok'


def test_configure_logging_handlers(clean_logger, tmp_path):
    logfile = tmp_path / 'cf.log'
    logger = configure_logging(filename=str(logfile), level='INFO', stream=True)
    handlers = non_null_handlers(logger)
    assert len(handlers) == 2
    assert any(isinstance(h, RotatingFileHandler) for h in handlers)
    assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in handlers)
    assert logger.level == logging.INFO
    assert logger.propagate is False

    logging.getLogger('cryptofeed.exchanges.test').info('hello')
    handlers[0].flush()
    assert 'hello' in logfile.read_text()


def test_configure_logging_noop_when_configured(clean_logger, tmp_path):
    configure_logging(filename=str(tmp_path / 'a.log'))
    before = non_null_handlers(clean_logger)
    configure_logging(filename=str(tmp_path / 'b.log'), stream=True)
    assert non_null_handlers(clean_logger) == before
    assert not (tmp_path / 'b.log').exists()


def test_configure_logging_respects_host_config(clean_logger):
    own = logging.StreamHandler()
    clean_logger.addHandler(own)
    logger = configure_logging(filename='never.log', stream=True)
    assert non_null_handlers(logger) == [own]
    assert logger.propagate is True


def test_feedhandler_log_disabled(clean_logger):
    FeedHandler(config={'log': {'disabled': True}})
    assert non_null_handlers(clean_logger) == []


def test_feedhandler_configures_from_stanza(clean_logger, tmp_path):
    logfile = tmp_path / 'fh.log'
    FeedHandler(config={'log': {'filename': str(logfile), 'level': 'INFO'}})
    handlers = non_null_handlers(clean_logger)
    assert any(isinstance(h, RotatingFileHandler) and h.baseFilename == str(logfile) for h in handlers)
    assert clean_logger.level == logging.INFO


def test_unknown_config_key_warns(clean_logger, caplog):
    with caplog.at_level(logging.WARNING, logger='cryptofeed.feedhandler'):
        FeedHandler(config={'log': {'disabled': True}, 'uvlop': True})
    warnings = [r.getMessage() for r in caplog.records]
    assert any("unknown top-level key 'uvlop'" in w and "did you mean 'uvloop'" in w for w in warnings)


def test_known_and_exchange_keys_do_not_warn(clean_logger, caplog):
    config = {
        'log': {'disabled': True},
        'uvloop': False,
        'ignore_invalid_instruments': True,
        'coinbase': {'key_id': 'a', 'key_secret': 'b'},
        'crypto.com': {'key_id': 'a', 'key_secret': 'b'},
    }
    with caplog.at_level(logging.WARNING, logger='cryptofeed.feedhandler'):
        FeedHandler(config=config)
    assert not any('unknown top-level key' in str(r.msg) for r in caplog.records)
