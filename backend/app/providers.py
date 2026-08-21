import re
from datetime import datetime
from bs4 import BeautifulSoup
import httpx

from .models import StockQuote, WarrantMetrics

BASE_URL = "https://newjust.masterlink.com.tw/Z/ZC/ZCA/zcastkwar8840_AQ{code}.djhtm"


def _number(pattern: str, text: str, *, default: float | None = None) -> float:
    match = re.search(pattern, text, re.I)
    if not match:
        if default is not None:
            return default
        raise ValueError(f"缺少欄位：{pattern}")
    return float(match.group(1).replace(",", ""))


def parse_warrant_page(html: str, code: str) -> tuple[str, StockQuote, WarrantMetrics]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "403 - Forbidden" in text or "Access is denied" in text:
        raise PermissionError("權證資料來源拒絕程式存取，請稍後再試或改接授權行情 API")
    header = re.search(r"([^\s(]+)\s*\(" + re.escape(code) + r"\)", text)
    if not header:
        raise ValueError("找不到權證，請確認六碼代號")
    warrant_name = header.group(1)

    # 頁面標的列的代號可能被前端腳本省略；名稱由權證名稱去除券商/日期尾碼推導，代號優先從連結取得。
    stock_code = ""
    stock_name_from_table = ""
    exercise_ratio = None

    # 行情表的「執行比例」是欄名，真正數值位於「標的」資料列的同一欄。
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        ratio_index = None
        for row in rows:
            cells = row.find_all(["th", "td"])
            values = [cell.get_text(" ", strip=True) for cell in cells]
            if ratio_index is None:
                ratio_index = next((i for i, value in enumerate(values) if "執行比例" in value), None)
                if ratio_index is not None:
                    continue
            if ratio_index is not None and any(value == "標的" for value in values):
                if ratio_index < len(values):
                    match = re.search(r"\d+(?:\.\d+)?", values[ratio_index].replace(",", ""))
                    if match:
                        exercise_ratio = float(match.group())
                joined = " ".join(values)
                # Avoid matching digit sequences that are part of decimal numbers
                # (e.g. the "0.0900" exercise ratio) by asserting the match
                # is not immediately preceded by a digit or a dot.
                target = re.search(r"(?<![\d.])(\d{4,6})\b\s*([^\s\d]+)?", joined)
                if target and target.group(1) != code:
                    stock_code = target.group(1)
                    stock_name_from_table = target.group(2) or ""
                break
        if exercise_ratio is not None:
            break

    for link in soup.find_all("a", href=True):
        candidate = re.search(r"(?:a=|_)(\d{4,6})(?:\D|$)", link["href"], re.I)
        if not stock_code and candidate and candidate.group(1) != code:
            stock_code = candidate.group(1)
            break
    known = {"067185": ("6770", "力積電")}
    fallback_code, fallback_name = known.get(code, ("", re.sub(r"(?:中信|元大|國泰|群益|凱基|永豐|富邦|統一|兆豐|元富|第一金|玉山).*$", "", warrant_name)))
    fallback_name = stock_name_from_table or fallback_name
    if not fallback_code and fallback_name:
        try:
            import twstock
            match = next((item.code for item in twstock.codes.values() if item.name == fallback_name), "")
            fallback_code = match
        except Exception:
            pass
    stock_code = stock_code or fallback_code
    if not stock_code:
        raise ValueError("來源頁未提供標的代號，請稍後再試")

    expiry_match = re.search(r"到期日期\s*(\d{3})/(\d{1,2})/(\d{1,2})", text)
    if not expiry_match:
        raise ValueError("缺少到期日期")
    expiry = f"{int(expiry_match.group(1)) + 1911:04d}-{int(expiry_match.group(2)):02d}-{int(expiry_match.group(3)):02d}"
    label_match = re.search(r"價內外程度\s*[-+]?\d+(?:\.\d+)?%?\s*(價內|價外|價平)?", text)
    if exercise_ratio is None:
        # 純文字頁面備援：容許「標的 6770 力積電 0.0900」的形式。
        direct = re.search(r"執行比例\s*([\d.]+)", text)
        target_row = re.search(r"標的(?:\s+\d{4,6})?(?:\s+[^\s\d]+)?\s+([01](?:\.\d+)?)", text)
        if direct:
            exercise_ratio = float(direct.group(1))
        elif target_row:
            exercise_ratio = float(target_row.group(1))
        else:
            raise ValueError("缺少欄位：執行比例")

    metrics = WarrantMetrics(
        days_to_expiry=int(_number(r"距到期日\(天\)\s*(\d+)", text)),
        strike_price=_number(r"目前履約價\s*([\d,.]+)", text),
        warrant_price=_number(r"權證價格\s*([\d,.]+)", text),
        exercise_ratio=exercise_ratio,
        delta=_number(r"Delta\s*([-\d.]+)", text),
        theta=_number(r"Theta\s*([-\d.]+)", text),
        moneyness_percent=_number(r"價內外程度\s*([-+\d.]+)%?", text),
        moneyness_label=label_match.group(1) if label_match and label_match.group(1) else "未標示",
        effective_leverage=_number(r"有效槓桿\s*([\d.]+)", text),
        expiry_date=expiry,
    )
    quote = StockQuote(code=stock_code, name=fallback_name, source="待取得")
    return warrant_name, quote, metrics


async def fetch_warrant(code: str) -> tuple[str, StockQuote, WarrantMetrics]:
    # 此固定公開來源的舊憑證鏈缺少 Python 3.14 要求的 SKI；僅此 client 關閉驗證。
    async with httpx.AsyncClient(timeout=12, verify=False, headers={"User-Agent": "Mozilla/5.0 WarrantScore/1.0"}) as client:
        response = await client.get(BASE_URL.format(code=code))
        response.raise_for_status()
        response.encoding = "big5"
    return parse_warrant_page(response.text, code)


def fetch_stock_quote(stock: StockQuote) -> tuple[StockQuote, str | None]:
    try:
        import twstock
        data = twstock.realtime.get(stock.code)
        if data.get("success"):
            rt, info = data["realtime"], data["info"]
            def f(key):
                value = rt.get(key)
                return float(value) if value not in (None, "-", "") else None
            return StockQuote(code=stock.code, name=info.get("name") or stock.name, price=f("latest_trade_price"), open=f("open"), high=f("high"), low=f("low"), volume=int(float(rt.get("accumulate_trade_volume") or 0)), source="twstock / TWSE", quoted_at=info.get("time")), None
    except Exception:
        pass

    try:
        import yfinance as yf
        warning = None
        frame = None
        symbol_used = None
        for suffix in (".TW", ".TWO"):
            candidate = yf.Ticker(stock.code + suffix).history(period="5d", interval="1d", auto_adjust=False)
            if not candidate.empty:
                frame, symbol_used = candidate, stock.code + suffix
                break
        if frame is not None:
            row = frame.iloc[-1]
            return StockQuote(code=stock.code, name=stock.name, price=float(row["Close"]), open=float(row["Open"]), high=float(row["High"]), low=float(row["Low"]), volume=int(row["Volume"]), source=f"yfinance ({symbol_used})", quoted_at=str(frame.index[-1])), "目前顯示最近交易日日線，非即時行情。"
    except Exception:
        warning = "標的行情來源暫時無法連線。"
    return stock, warning or "查無標的行情。"
