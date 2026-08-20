from app.models import WarrantMetrics
from app.scoring import calculate_score


def test_score_is_explainable_and_bounded():
    metrics = WarrantMetrics(days_to_expiry=96, strike_price=90, warrant_price=.88, exercise_ratio=.09, delta=.0436, theta=-.0079, moneyness_percent=16.78, moneyness_label="價外", effective_leverage=3.711, expiry_date="2026-11-17")
    score, rating, items = calculate_score(metrics)
    assert 0 <= score <= 100
    assert rating in {"優良", "良好", "普通", "偏弱"}
    assert len(items) == 8
    assert score == sum(item.score for item in items)

