'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging


FORMAT = logging.Formatter('%(asctime)-15s : %(levelname)s : %(message)s')


def get_logger(name, filename, level=logging.WARNING):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    stream = logging.StreamHandler()
    stream.setFormatter(FORMAT)
    logger.addHandler(stream)

    fh = logging.FileHandler(filename)
    fh.setFormatter(FORMAT)
    logger.addHandler(fh)
    logger.propagate = False
    return logger
