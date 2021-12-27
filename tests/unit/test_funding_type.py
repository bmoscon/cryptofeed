from cryptofeed.exchange import Exchange
from cryptofeed.types import Funding

import datetime
from decimal import Decimal


def test_funding_to_dict():
    # data and data2 is example funding data from FTX
    data = {
        "success": True,
        "result": [
            {
                "future": "MER-PERP",
                "rate": Decimal("-0.000001"),
                "time": datetime.datetime(
                    2021, 12, 26, 20, 0, tzinfo=datetime.timezone.utc
                ),
            },
            {
                "future": "MER-PERP",
                "rate": Decimal("0.000015"),
                "time": datetime.datetime(
                    2021, 12, 26, 19, 0, tzinfo=datetime.timezone.utc
                ),
            },
        ],
    }

    data2 = {
        "success": True,
        "result": {
            "volume": Decimal("3391482.0"),
            "nextFundingRate": Decimal("0.0"),
            "nextFundingTime": datetime.datetime(
                2021, 12, 26, 21, 0, tzinfo=datetime.timezone.utc
            ),
            "openInterest": Decimal("1164922.0"),
        },
    }
    data["predicted_rate"] = Decimal(data2["result"]["nextFundingRate"])

    f = Funding(
        "FTX",
        "MER-PERP",
        None,
        data["result"][0]["rate"],
        Exchange.timestamp_normalize(data2["result"]["nextFundingTime"]),
        Exchange.timestamp_normalize(data["result"][0]["time"]),
        predicted_rate=data["predicted_rate"],
        raw=[data, data2],
    )
    f_dict = f.to_dict(numeric_type=float, none_to=None)

    assert f_dict["predicted_rate"] == data["predicted_rate"]
