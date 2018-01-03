from setuptools import setup
from setuptools import find_packages


setup(
    name="cryptofeed",
    version="0.7.0",
    author="Bryant Moscon",
    author_email="bmoscon@gmail.com",
    description=("Cryptocurrency feed handler and synthetic NBBO feed"),
    license="XFree86",
    keywords=["cryptocurrency", "bitcoin", "btc", "feed handler", "market feed", "market data"],
    url="https://github.com/bmoscon/cryptofeed",
    packages=find_packages(exclude=['tests']),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    setup_requires=["requests",
                    "websockets",
                   ],
)
