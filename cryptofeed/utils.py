import asyncio
from time import time
from datetime import datetime
import json
from decimal import Decimal


async def call_periodically(interval, func, *args, **kwargs):
    """
    :param func: callable
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


class JSONDatetimeDecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return str(obj)
        return json.JSONEncoder.default(self, obj)
