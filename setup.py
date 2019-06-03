'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import sys

from setuptools import setup
from setuptools import find_packages
from setuptools.command.test import test as TestCommand

ld = None
try:
    import pypandoc
    ld = pypandoc.convert_file('README.md', 'rst', format='markdown_github')
except BaseException:
    pass


class Test(TestCommand):
    def run_tests(self):
        import pytest
        errno = pytest.main([])
        sys.exit(errno)


setup(
    name="cryptofeed",
    version="0.24.0",
    author="Bryant Moscon",
    author_email="bmoscon@gmail.com",
    description=("Cryptocurrency feed handler and synthetic NBBO feed"),
    long_description=ld,
    long_description_content_type='text/x-rst',
    license="XFree86",
    keywords=["cryptocurrency", "bitcoin", "btc", "feed handler", "market feed", "market data"],
    url="https://github.com/bmoscon/cryptofeed",
    packages=find_packages(exclude=['tests']),
    package_data={'': ['rest/config.yaml']},
    cmdclass={'test': Test},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    tests_require=["pytest"],
    install_requires=[
        "requests>=2.18.4",
        "websockets>=7.0",
        "sortedcontainers>=1.5.9",
        "pandas",
        "pyyaml",
        "aiohttp",
        "aiodns",
        "cchardet"
    ],
    extras_require={
        'redis': ['aioredis'],
        'arctic': ['arctic'],
        'zmq': ['pyzmq'],
        'mongo': ['motor'],
        'kafka': ['aiokafka']
    },
)
