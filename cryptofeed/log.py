'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from logging.handlers import RotatingFileHandler


FORMAT = logging.Formatter('%(asctime)-15s : %(levelname)s : %(message)s')


def get_logger(name, filename, level=logging.WARNING):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    stream = logging.StreamHandler()
    stream.setFormatter(FORMAT)
    logger.addHandler(stream)

    fh = RotatingFileHandler(filename, maxBytes=10 * 1024 * 1024, backupCount=10)
    fh.setFormatter(FORMAT)
    logger.addHandler(fh)
    logger.propagate = False
    return logger
