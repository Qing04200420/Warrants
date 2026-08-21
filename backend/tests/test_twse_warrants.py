import pytest

from app import database
from app.twse_warrants import _issuer_filter, _postback_form, parse_market_rows
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


@pytest.mark.parametrize(
    ("issuer", "company_name", "company_code"),
    [
        ("第一金", "第一金證券", "5380"),
        ("統一", "統一綜合證券", "5850"),
        ("中信", "中國信託綜合證券", "6160"),
        ("兆豐", "兆豐證券", "7000"),
        ("國票", "國票綜合證券", "7790"),
        ("康和", "康和綜合證券", "8450"),
        ("國泰", "國泰綜合證券", "8880"),
        ("群益", "群益金鼎證券", "9100"),
        ("凱基", "凱基證券", "9200"),
        ("富邦", "富邦綜合證券", "9600"),
        ("元大", "元大證券", "9800"),
        ("永豐", "永豐金證券", "9A00"),
        ("台新", "台新綜合證券", "9B00"),
    ],
)
def test_all_issuer_aliases_match_twse_full_company_names(issuer, company_name, company_code):
    page = BeautifulSoup(
        f'<select name="COMPANY"><option value="{company_code}"> {company_name} </option></select>',
        "html.parser",
    )

    assert _issuer_filter(page, f"力積電{issuer}5B購04") == company_code


def test_page_postback_keeps_stock_and_company_filters():
    page = BeautifulSoup(
        '<input type="hidden" name="__VIEWSTATE" value="state">',
        "html.parser",
    )

    form = _postback_form(page, "3017", "9100", "GridCenter", 2)

    assert form["stockNo"] == "3017"
    assert form["COMPANY"] == "9100"
    assert form["__VIEWSTATE"] == "state"
    assert form["__EVENTTARGET"] == "GridCenter"
    assert form["__EVENTARGUMENT"] == "Page$2"
    assert "BtnQuery" not in form
