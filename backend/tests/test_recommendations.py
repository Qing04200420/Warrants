from datetime import date

from app.recommendations import recommend_warrants
from app.twse_openapi import OfficialWarrant


def warrant(code, *, call_put="C", strike=100, last_trading=date(2027, 1, 15), name="台積電"):  # noqa: E501
    return OfficialWarrant(
        code=code,
        name=f"台積電測試{code}",
        call_put=call_put,
        underlying_name=name,
        strike_price=strike,
        exercise_ratio=0.1,
        last_trading_date=last_trading,
        expiry_date=last_trading,
        data_date=date(2026, 8, 26),
    )


def test_recommendations_keep_calls_and_rank_near_money_first():
    items = recommend_warrants(
        [
            warrant("000001", strike=112),
            warrant("000002", strike=101),
            warrant("000003", strike=99, call_put="P"),
            warrant("000004", strike=100, name="聯發科"),
        ],
        underlying_name="台積電",
        stock_price=100,
        as_of=date(2026, 8, 26),
    )

    assert [item.code for item in items] == ["000002", "000001"]
    assert items[0].moneyness == "價外"
    assert items[0].days_to_last_trading == 142


def test_recommendations_exclude_contracts_with_less_than_30_days():
    items = recommend_warrants(
        [
            warrant("000001", last_trading=date(2026, 9, 10)),
            warrant("000002", strike=150),
        ],
        underlying_name="台積電",
        stock_price=100,
        as_of=date(2026, 8, 26),
    )

    assert items == []
