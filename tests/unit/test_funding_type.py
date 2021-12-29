from cryptofeed.exchange import Exchange
from cryptofeed.types import Funding

import datetime
from decimal import Decimal


def test_funding_to_dict():
    data = {
        "exchange": "FTX",
        "symbol": "BTC-USD-PERP",
        "mark_price": Decimal("50000"),
        "rate": Decimal("0.0002"),
        "next_funding_time": Exchange.timestamp_normalize(
            datetime.datetime(2021, 12, 26, 21, 0, tzinfo=datetime.timezone.utc)
        ),
        "predicted_rate": Decimal("0.0"),
        "timestamp": Exchange.timestamp_normalize(
            datetime.datetime(2021, 12, 26, 20, 0, tzinfo=datetime.timezone.utc)
        ),
    }

    f = Funding(
        **data,
        raw=data,
    )
    f_dict = f.to_dict(numeric_type=float, none_to=None)

    assert f_dict["predicted_rate"] == data["predicted_rate"]
