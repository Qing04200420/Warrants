from app.providers import parse_warrant_page
import pytest


def test_parse_reference_shape():
    html = """<html><body>力積電中信5B購04(067185)基本資料 執行比例 0.0900
    到期日期 115/11/17 目前履約價 90.00 距到期日(天) 96 權證價格 0.88
    Delta 0.0436 價內外程度 16.78% 價外 Theta -0.0079 有效槓桿 3.7110</body></html>"""
    name, stock, metrics = parse_warrant_page(html, "067185")
    assert name == "力積電中信5B購04"
    assert stock.code == "6770"
    assert metrics.exercise_ratio == .09
    assert metrics.expiry_date == "2026-11-17"


def test_rejects_disguised_forbidden_page():
    with pytest.raises(PermissionError):
        parse_warrant_page("<h2>403 - Forbidden: Access is denied.</h2>", "067185")


def test_ratio_is_read_from_target_table_column():
    html = """<html><body>力積電中信5B購04(067185)基本資料
    <table><tr><th>商品</th><th>名稱</th><th>執行比例</th><th>收盤價</th></tr>
    <tr><td>權證</td><td>067185 力積電中信5B購04</td><td>--</td><td>0.88</td></tr>
    <tr><td>標的</td><td>6770 力積電</td><td>0.0900</td><td>74.90</td></tr></table>
    到期日期 115/11/17 目前履約價 90.00 距到期日(天) 96 權證價格 0.88
    Delta 0.0436 價內外程度 16.78% 價外 Theta -0.0079 有效槓桿 3.7110</body></html>"""
    _, stock, metrics = parse_warrant_page(html, "067185")
    assert stock.code == "6770"
    assert stock.name == "力積電"
    assert metrics.exercise_ratio == .09
