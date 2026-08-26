from datetime import date

import pytest

from app.pricing import price_warrant, trading_days_between


def test_call_warrant_price_is_split_into_intrinsic_and_time_value():
    result = price_warrant(
        call_put="C",
        stock_price=130,
        strike_price=120,
        exercise_ratio=0.1,
        trading_days=63,
        volatility=0.3,
        risk_free_rate=0.015,
    )

    assert result.intrinsic_value == pytest.approx(1)
    assert result.theoretical_price == pytest.approx(
        result.intrinsic_value + result.time_value
    )
    assert result.theoretical_price > result.intrinsic_value


def test_put_warrant_has_value_when_underlying_is_below_strike():
    result = price_warrant(
        call_put="P",
        stock_price=80,
        strike_price=100,
        exercise_ratio=0.05,
        trading_days=30,
        volatility=0.25,
        risk_free_rate=0.015,
    )

    assert result.intrinsic_value == pytest.approx(1)
    assert result.theoretical_price >= 1
    assert result.delta < 0


def test_trading_days_excludes_weekend_and_valuation_day():
    assert trading_days_between(date(2026, 8, 21), date(2026, 8, 24)) == 1
    assert trading_days_between(date(2026, 8, 21), date(2026, 8, 24), {date(2026, 8, 24)}) == 0
    assert trading_days_between(date(2026, 8, 24), date(2026, 8, 24)) == 0
