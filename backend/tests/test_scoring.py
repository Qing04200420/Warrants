from app.models import WarrantMetrics
from app.scoring import calculate_score


def metrics(**overrides):
    values = {
        "days_to_expiry": 96,
        "strike_price": 90,
        "warrant_price": .88,
        "exercise_ratio": .09,
        "delta": .0436,
        "theta": -.0079,
        "moneyness_percent": 16.78,
        "moneyness_label": "價外",
        "effective_leverage": 3.711,
        "expiry_date": "2026-11-17",
    }
    return WarrantMetrics(**(values | overrides))


def test_score_is_explainable_and_bounded():
    score, rating, items = calculate_score(metrics())
    assert 0 <= score <= 100
    assert rating in {"優良", "良好", "普通", "偏弱"}
    # scoring now includes IV and liquidity related items; expect 10 items
    assert len(items) == 10
    assert score == sum(item.score for item in items)


def test_missing_market_data_is_labeled_and_given_neutral_scores():
    _, _, items = calculate_score(metrics())
    by_key = {item.key: item for item in items}

    assert by_key["iv_reasonable"].score == 7.5
    assert by_key["iv_stability"].score == 5.0
    assert by_key["liquidity"].score == 7.5
    assert by_key["iv_reasonable"].note == "資料缺失，採中性分"
    assert by_key["iv_stability"].note == "資料缺失，採中性分"
    assert by_key["liquidity"].note == "買賣價差資料缺失（採中性分）；掛單量資料缺失（採中性分）"
    assert all("None" not in item.note for item in items)
    assert all("vol=0" not in item.note for item in items)


def test_real_zero_bid_volume_is_not_treated_as_missing():
    score, rating, items = calculate_score(metrics(bid_volume=0))

    assert score == 0
    assert rating == "淘汰"
    assert items[0].key == "eliminated"
    assert items[0].note == "委買量 0 < 50"

