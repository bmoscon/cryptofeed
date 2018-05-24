import asyncio
from time import time


async def call_periodically(interval, func, *args, **kwargs):
    """
    schedule a function to run periodically
    `interval` must be longer than execution time for `func` for
    timing to be accurate

    :param func: callable MUST BE ASYNC
    :param interval: int interval in seconds
    :param args: list args to call with
    :param kwargs: dict keyword args to call with
    :return: None
    """
    start_time = time()
    while True:
        await func(*args, **kwargs)
        await asyncio.sleep(
            interval - ((time() - start_time) % interval)
        )
