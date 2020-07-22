'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import sys

from setuptools import setup
from setuptools import find_packages
from setuptools.command.test import test as TestCommand

# Read the contents of README.md and CHANGES.md files
from os import path
root_repo_dir = path.abspath(path.dirname(__file__))
with open(path.join(root_repo_dir, 'README.md'), encoding='utf-8') as readme_file:
    readme = readme_file.read()
with open(path.join(root_repo_dir, 'CHANGES.md'), encoding='utf-8') as changes_file:
    changes = changes_file.read()

class Test(TestCommand):
    def run_tests(self):
        import pytest
        errno = pytest.main(['tests/'])
        sys.exit(errno)


setup(
    name="cryptofeed",
    version="1.5.0",
    author="Bryant Moscon",
    author_email="bmoscon@gmail.com",
    description="Cryptocurrency feed handler and synthetic NBBO feed",
    long_description=readme + '\n\n' + changes,
    long_description_content_type='text/markdown',
    license="XFree86",
    keywords=["cryptocurrency", "bitcoin", "btc", "feed handler", "market feed", "market data"],
    url="https://github.com/bmoscon/cryptofeed",
    packages=find_packages(exclude=['tests']),
    package_data={'': ['rest/config.yaml']},
    cmdclass={'test': Test},
    python_requires='>=3.7',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8"
    ],
    tests_require=["pytest"],
    install_requires=[
        "requests>=2.18.4",
        "websockets>=7.0",
        "sortedcontainers>=1.5.9",
        "pandas",
        "pyyaml",
        "aiohttp==3.6.2",
        "aiofile",
        'yapic.json>=1.4.3'
    ],
    extras_require={
        'redis': ['aioredis'],
        'arctic': ['arctic'],
        'zmq': ['pyzmq'],
        'mongo': ['motor'],
        'kafka': ['aiokafka'],
        'rabbit': ['aio_pika', 'pika'],
        'postgres': ['asyncpg'],
        'speedups': ['aiodns>=1.1', 'cchardet'],
        'all': ['aioredis', 'arctic', 'pyzmq', 'motor', 'aiokafka', 'aio_pika', 'pika', 'asyncpg', 'aiodns>=1.1', 'cchardet'],
    },
)
