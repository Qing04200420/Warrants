from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.models import StockScoreRequest
from app.stock_history import DailyBar, StockHistory, _daily_from_kbars
from app.stock_scoring import calculate_stock_score


def make_bars(count=100, start=100, step=0.5):
    first = date(2026, 1, 1)
    result = []
    for index in range(count):
        close = start + index * step
        result.append(
            DailyBar(
                day=first + timedelta(days=index),
                open=close - 0.2,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1000 + index * 5,
            )
        )
    return result


def test_bullish_stock_score_has_all_groups_and_totals_100_points():
    history = StockHistory(
        code="2330",
        name="台積電",
        bars=make_bars(),
        index_bars=make_bars(start=20000, step=10),
        source="test",
    )
    request = StockScoreRequest(
        code="2330",
        entry_price=145,
        stop_loss_price=140,
        target_price=160,
    )

    result = calculate_stock_score(history, request)

    assert sum(item.max_score for item in result.items) == 100
    assert result.daily["ideal_order"] is True
    assert result.weekly["bullish"] is True
    assert result.risk_reward["ratio"] == pytest.approx(3)
    assert result.score >= 80
    assert {item.group for item in result.items} == {
        "大盤環境", "日線趨勢", "週線趨勢", "價格結構", "量價關係", "動能指標", "風險報酬"
    }


def test_long_plan_requires_stop_below_entry_below_target():
    with pytest.raises(ValidationError):
        StockScoreRequest(code="2330", entry_price=100, stop_loss_price=105, target_price=120)


def test_minute_kbars_are_aggregated_to_daily_ohlcv():
    bars = _daily_from_kbars([{
        "datetime": ["2026-08-25T09:01:00", "2026-08-25T09:02:00"],
        "Open": [100, 102],
        "High": [103, 105],
        "Low": [99, 101],
        "Close": [102, 104],
        "Volume": [10, 20],
    }])

    assert len(bars) == 1
    assert bars[0].open == 100
    assert bars[0].high == 105
    assert bars[0].low == 99
    assert bars[0].close == 104
    assert bars[0].volume == 30
