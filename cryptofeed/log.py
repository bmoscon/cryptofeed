'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from logging.handlers import RotatingFileHandler


FORMAT = logging.Formatter('%(asctime)-15s : %(levelname)s : %(name)s : %(message)s')


def configure_logging(filename: str = None, level='WARNING', stream: bool = False, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 10) -> logging.Logger:
    logger = logging.getLogger('cryptofeed')
    if any(not isinstance(h, logging.NullHandler) for h in logger.handlers):
        return logger
    logger.setLevel(level)
    if filename:
        fh = RotatingFileHandler(filename, maxBytes=max_bytes, backupCount=backup_count)
        fh.setFormatter(FORMAT)
        logger.addHandler(fh)
    if stream:
        sh = logging.StreamHandler()
        sh.setFormatter(FORMAT)
        logger.addHandler(sh)
    if filename or stream:
        logger.propagate = False
    return logger
