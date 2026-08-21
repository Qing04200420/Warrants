from app.providers import parse_warrant_page

html = """<html><body>力積電中信5B購04(067185)基本資料 執行比例 0.0900
到期日期 115/11/17 目前履約價 90.00 距到期日(天) 96 權證價格 0.88
Delta 0.0436 價內外程度 16.78% 價外 Theta -0.0079 有效槓桿 3.7110</body></html>"""

name, stock, metrics = parse_warrant_page(html, "067185")
print('name=', name)
print('stock.code=', stock.code)
print('stock.name=', stock.name)
print('metrics.exercise_ratio=', metrics.exercise_ratio)
print('metrics.expiry_date=', metrics.expiry_date)
