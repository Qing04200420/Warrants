import pytest

from app.twse_openapi import parse_holiday_records, parse_roc_date, parse_warrant_records


def test_parses_latest_official_terms_and_ratio_per_thousand():
    rows = [{
        "出表日期": "1150824",
        "權證代號": "03002T",
        "權證簡稱": "台積電群益5A售12",
        "權證類型": "認售",
        "標的證券/指數": "台積電",
        "最新標的履約配發數量(每仟單位權證)": "19.00",
        "最新履約價格(元)/履約指數": "1855.0500",
        "最後交易日": "1151014",
        "履約截止日": "1151016",
    }]

    item = parse_warrant_records(rows)["03002T"]

    assert item.call_put == "P"
    assert item.strike_price == pytest.approx(1855.05)
    assert item.exercise_ratio == pytest.approx(0.019)
    assert item.last_trading_date.isoformat() == "2026-10-14"


def test_roc_date_parser():
    assert parse_roc_date("115/08/24").isoformat() == "2026-08-24"


def test_holiday_parser_does_not_exclude_announced_trading_days():
    rows = [
        {"Name": "中秋節", "Date": "1150925"},
        {"Name": "國曆新年開始交易日", "Date": "1150102"},
        {"Name": "春節前最後交易日", "Date": "1150211"},
    ]

    assert parse_holiday_records(rows) == {parse_roc_date("1150925")}
