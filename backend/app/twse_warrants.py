"""TWSE 權證資訊揭露平台的盤後資料查詢與解析。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from time import monotonic
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import httpx


BASE_URL = "https://warrants.twse.com.tw"
# 平台的 Period=14 代表查詢 14 日委買 IV 統計欄位。
QUERY_PERIOD = "14"
# 避免同一權證在短時間內重複觸發多次 WebForms 查詢。
CACHE_TTL_SECONDS = 4 * 60 * 60
# TWSE 依價內外程度拆成三個 GridView，三者都可能包含目標權證。
GRID_IDS = ("GridCenter", "GridUp", "GridDown")
# 權證簡稱採券商縮寫，但 TWSE 下拉選單可能使用公司完整名稱。
ISSUER_ALIASES = {
    "中信": ("中信", "中國信託"),
    "元大": ("元大",),
    "國泰": ("國泰",),
    "群益": ("群益",),
    "凱基": ("凱基",),
    "永豐": ("永豐",),
    "富邦": ("富邦",),
    "統一": ("統一",),
    "兆豐": ("兆豐",),
    "元富": ("元富",),
    "第一金": ("第一金",),
    "玉山": ("玉山",),
    "台新": ("台新",),
    "新光": ("新光",),
}


@dataclass(frozen=True)
class TwseWarrantMarketData:
    """單一權證的一筆 TWSE 盤後造市資料。"""
    implied_vol: float | None
    period_max_iv_change: float | None
    bid_ask_spread: float | None
    bid_volume: int | None
    ask_volume: int | None
    observed_on: str


# key 為（標的代號、權證代號），value 為（快取時間、查詢結果）。
_row_cache: dict[tuple[str, str], tuple[float, TwseWarrantMarketData | None]] = {}


def _soup(response: httpx.Response) -> BeautifulSoup:
    # 平台仍使用 Big5；不能完全信任中介伺服器回傳的 charset 標頭。
    return BeautifulSoup(response.content, "html.parser", from_encoding="big5")


def _hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    """擷取 ASP.NET WebForms postback 所需的 ViewState 等隱藏欄位。"""
    return {
        node["name"]: node.get("value", "")
        for node in soup.select('input[type="hidden"][name]')
    }


def _percent(value: str) -> float | None:
    """把網頁百分比字串轉成小數；破折號代表官方沒有資料。"""
    cleaned = value.replace("%", "").replace(",", "").strip()
    if not cleaned or cleaned in {"-", "--"}:
        return None
    try:
        return float(cleaned) / 100
    except ValueError:
        return None


def _integer(value: str) -> int | None:
    """解析掛單量，並區分真正的 0 與缺值「-」。"""
    cleaned = value.replace(",", "").strip()
    if not cleaned or cleaned in {"-", "--"}:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _row_values(row) -> list[str]:
    return [cell.get_text(" ", strip=True) for cell in row.find_all("td", recursive=False)]


def parse_market_rows(html: str, observed_on: str | None = None) -> dict[str, TwseWarrantMarketData]:
    """解析 TWSE 三個結果表格，回傳以權證代號索引的盤後資料。"""
    soup = BeautifulSoup(html, "html.parser")
    date_value = observed_on or datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    result: dict[str, TwseWarrantMarketData] = {}
    for table in soup.select("table.query-grid"):
        for row in table.find_all("tr"):
            values = _row_values(row)
            if len(values) < 19:
                continue
            code = values[0].strip().upper()
            if not re.fullmatch(r"[0-9A-Z]{6}", code):
                continue

            # 委買 IV 最接近投資人賣回時的造市水準；若缺少委買報價，
            # 才依序改用委賣 IV、期間委買 IV、收盤 IV。
            implied_vol = next(
                (value for value in (_percent(values[5]), _percent(values[6]), _percent(values[7]), _percent(values[16])) if value is not None),
                None,
            )
            result[code] = TwseWarrantMarketData(
                implied_vol=implied_vol,
                period_max_iv_change=_percent(values[9]),
                bid_ask_spread=_percent(values[12]),
                bid_volume=_integer(values[13]),
                ask_volume=_integer(values[14]),
                observed_on=date_value,
            )
    return result


def _parse_market_rows_from_soup(soup: BeautifulSoup, observed_on: str) -> dict[str, TwseWarrantMarketData]:
    return parse_market_rows(str(soup), observed_on)


def _issuer_filter(query_page: BeautifulSoup, warrant_name: str) -> str:
    """把權證簡稱中的券商縮寫對應到 TWSE COMPANY 下拉選單值。"""
    issuer = next((alias for alias in ISSUER_ALIASES if alias in warrant_name), "")
    if not issuer:
        return ""
    for option in query_page.select('select[name="COMPANY"] option[value]'):
        option_text = option.get_text(" ", strip=True)
        if any(candidate in option_text for candidate in ISSUER_ALIASES[issuer]):
            return option.get("value", "")
    return ""


def _query_form(soup: BeautifulSoup, underlying_code: str, company: str) -> dict[str, str]:
    """組合第一次送往 Query.aspx 的完整 WebForms 查詢表單。"""
    data = _hidden_fields(soup)
    data.update(
        {
            "stockNo": underlying_code,
            "COMPANY": company,
            "duration1": "",
            "duration2": "",
            "PriceType1": "",
            "priceDepth1": "",
            "PriceType2": "",
            "priceDepth2": "",
            "CPType": "",
            "Period": QUERY_PERIOD,
            "DDLScatterCol1": "BUY_IV",
            "DDLScatterCount": "10",
            "DDLScatterCol2": "PERIOD_BUY_IV",
            "BtnQuery": "查詢",
        }
    )
    return data


def _page_targets(soup: BeautifulSoup) -> list[tuple[str, int]]:
    """從 __doPostBack 連結擷取各 GridView 可翻閱的分頁。"""
    targets: set[tuple[str, int]] = set()
    pattern = re.compile(r"__doPostBack\('([^']+)','Page\$(\d+)'\)")
    for link in soup.select('a[href*="Page$"]'):
        match = pattern.search(link.get("href", ""))
        if match and match.group(1) in GRID_IDS:
            targets.add((match.group(1), int(match.group(2))))
    return sorted(targets, key=lambda item: (item[0], item[1]))


async def _fetch_rows(underlying_code: str, warrant_code: str, warrant_name: str) -> dict[str, TwseWarrantMarketData]:
    """完成同意頁、查詢頁及必要分頁的 WebForms 連線流程。"""
    headers = {"User-Agent": "Mozilla/5.0 WarrantScore/1.0"}
    async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=20, headers=headers) as client:
        # 第一步先載入聲明頁並帶回 ViewState，再送出「繼續」。
        landing = await client.get("/Default.aspx")
        landing.raise_for_status()
        accept = _hidden_fields(_soup(landing))
        accept["BTNConfirm"] = "繼續"
        query_response = await client.post("/Default.aspx", data=accept)
        query_response.raise_for_status()
        query_page = _soup(query_response)

        # stockNo 是標的股票代號，不是權證代號；券商篩選可大幅減少分頁。
        company = _issuer_filter(query_page, warrant_name)
        response = await client.post("/Query.aspx", data=_query_form(query_page, underlying_code, company))
        response.raise_for_status()
        first_page = _soup(response)
        observed_on = datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
        rows = _parse_market_rows_from_soup(first_page, observed_on)
        if warrant_code.upper() in rows:
            return rows

        # 一般在第一頁即可找到；若未找到，再模擬 GridView postback 翻頁。
        base_state = _hidden_fields(first_page)
        for grid, page in _page_targets(first_page):
            postback = dict(base_state)
            postback["__EVENTTARGET"] = grid
            postback["__EVENTARGUMENT"] = f"Page${page}"
            page_response = await client.post("/Query.aspx", data=postback)
            page_response.raise_for_status()
            rows.update(_parse_market_rows_from_soup(_soup(page_response), observed_on))
            if warrant_code.upper() in rows:
                break
        return rows


async def fetch_twse_warrant_market_data(
    underlying_code: str,
    warrant_code: str,
    warrant_name: str = "",
) -> TwseWarrantMarketData | None:
    """取得官方 TWSE 盤後權證資料，並以短期記憶體快取降低網站負載。"""
    cache_key = (underlying_code, warrant_code.upper())
    cached = _row_cache.get(cache_key)
    now = monotonic()
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    rows = await _fetch_rows(underlying_code, warrant_code, warrant_name)
    result = rows.get(warrant_code.upper())
    _row_cache[cache_key] = (now, result)
    return result
