'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import sys

from setuptools import setup
from setuptools import find_packages
from setuptools.command.test import test as TestCommand


class Test(TestCommand):
    def run_tests(self):
        import pytest
        errno = pytest.main([])
        sys.exit(errno)


setup(
    name="cryptofeed",
    version="0.14.0",
    author="Bryant Moscon",
    author_email="bmoscon@gmail.com",
    description=("Cryptocurrency feed handler and synthetic NBBO feed"),
    license="XFree86",
    keywords=["cryptocurrency", "bitcoin", "btc", "feed handler", "market feed", "market data"],
    url="https://github.com/bmoscon/cryptofeed",
    packages=find_packages(exclude=['tests']),
    cmdclass={'test': Test},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    tests_require=["pytest"],
    install_requires=[
        "requests>=2.18.4",
        "websockets>=5.0",
        "sortedcontainers>=1.5.9",
        "pandas",
        "pyyaml"
    ],
    extras_require={
        'redis': ['aioredis'],
    },
)
