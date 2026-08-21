import pytest

from app import database
from app.twse_warrants import _issuer_filter, parse_market_rows
from bs4 import BeautifulSoup


def _table_row(values):
    cells = "".join(f"<td>{value}</td>" for value in values)
    return f'<table class="query-grid"><tr>{cells}</tr></table>'


def test_parse_twse_after_close_market_fields():
    html = _table_row(
        [
            "03330T", "力積電群益5B售04", "60", "價外 22.36%", "0.1500",
            "110.08%", "110.46%", "110.11%", "110.69%", "0.10%",
            "0.64%", "1", "0.87%", "498", "49", "1.15", "110.96%",
            "0.88%", "群益金鼎",
        ]
    )

    item = parse_market_rows(html, "2026-08-21")["03330T"]

    assert item.implied_vol == pytest.approx(1.1008)
    assert item.period_max_iv_change == pytest.approx(0.001)
    assert item.bid_ask_spread == pytest.approx(0.0087)
    assert item.bid_volume == 498
    assert item.ask_volume == 49
    assert item.observed_on == "2026-08-21"


def test_parse_twse_dashes_as_missing_not_zero():
    html = _table_row(
        [
            "03317T", "力積電元大5B售10", "59", "價外 22.36%", "0.2000",
            "-", "-", "84.49%", "0.00%", "0.22%", "0.00%", "", "-",
            "498", "-", "1.00", "86.16%", "1.59%", "元大",
        ]
    )

    item = parse_market_rows(html)["03317T"]

    assert item.implied_vol == pytest.approx(0.8449)
    assert item.bid_ask_spread is None
    assert item.bid_volume == 498
    assert item.ask_volume is None


def test_iv_history_uses_one_sample_per_trading_date(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "warrants.db")
    database.init_db()

    std, count = database.record_iv_sample("03330T", "2026-08-20", 1.0)
    assert std is None
    assert count == 1

    std, count = database.record_iv_sample("03330T", "2026-08-21", 1.1)
    assert std == pytest.approx(0.05)
    assert count == 2

    std, count = database.record_iv_sample("03330T", "2026-08-21", 1.2)
    assert std == pytest.approx(0.1)
    assert count == 2


def test_issuer_alias_matches_twse_full_company_name():
    page = BeautifulSoup(
        '<select name="COMPANY"><option value="6160">中國信託綜合證券</option></select>',
        "html.parser",
    )

    assert _issuer_filter(page, "力積電中信5B購04") == "6160"
