"""股票與加權指數歷史日線；Shioaji 優先、Yahoo 僅作備援。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Generic, TypeVar
from zoneinfo import ZoneInfo

import httpx

from .broker import ShioajiHttpClient
from .twse_openapi import fetch_market_holidays


@dataclass(frozen=True)
class DailyBar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class StockHistory:
    code: str
    name: str
    bars: list[DailyBar]
    index_bars: list[DailyBar]
    source: str
    warning: str | None = None


@dataclass(frozen=True)
class _StockHistoryPart:
    code: str
    name: str
    bars: list[DailyBar]
    source: str
    warning: str | None = None


@dataclass(frozen=True)
class _IndexHistoryPart:
    bars: list[DailyBar]
    source: str
    warning: str | None = None


_CacheValue = TypeVar("_CacheValue")


@dataclass(frozen=True)
class _CacheEntry(Generic[_CacheValue]):
    value: _CacheValue
    expires_at: datetime


TAIPEI_TIMEZONE = ZoneInfo("Asia/Taipei")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(13, 30)
MARKET_CACHE_TTL = timedelta(minutes=10)

# 個股與大盤分開保存，讓不同股票的評分共用同一份加權指數資料。
_stock_cache: dict[str, _CacheEntry[_StockHistoryPart]] = {}
_index_cache: _CacheEntry[_IndexHistoryPart] | None = None
_stock_locks: dict[str, asyncio.Lock] = {}
_index_lock = asyncio.Lock()
_calendar_lock = asyncio.Lock()


def _as_taipei(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=TAIPEI_TIMEZONE)
    return now.astimezone(TAIPEI_TIMEZONE)


def _is_trading_day(day: date, holidays: frozenset[date] = frozenset()) -> bool:
    return day.weekday() < 5 and day not in holidays


def _next_market_open(now: datetime, holidays: frozenset[date] = frozenset()) -> datetime:
    now = _as_taipei(now)
    candidate_day = now.date()
    if _is_trading_day(candidate_day, holidays) and now.time() < MARKET_OPEN:
        return datetime.combine(candidate_day, MARKET_OPEN, TAIPEI_TIMEZONE)

    candidate_day += timedelta(days=1)
    while not _is_trading_day(candidate_day, holidays):
        candidate_day += timedelta(days=1)
    return datetime.combine(candidate_day, MARKET_OPEN, TAIPEI_TIMEZONE)


def _cache_expires_at(now: datetime, holidays: frozenset[date] = frozenset()) -> datetime:
    """盤中保留 10 分鐘；其餘時段保留到下一個交易日開盤。"""
    now = _as_taipei(now)
    if _is_trading_day(now.date(), holidays) and MARKET_OPEN <= now.time() < MARKET_CLOSE:
        close_at = datetime.combine(now.date(), MARKET_CLOSE, TAIPEI_TIMEZONE)
        return min(now + MARKET_CACHE_TTL, close_at)
    return _next_market_open(now, holidays)


def _cache_is_valid(entry: _CacheEntry | None, now: datetime) -> bool:
    return entry is not None and _as_taipei(now) < entry.expires_at


async def _load_market_holidays() -> frozenset[date]:
    """休市日取不到時退回週一至週五，避免行事曆服務拖垮評分。"""
    async with _calendar_lock:
        try:
            return frozenset(await fetch_market_holidays())
        except (httpx.HTTPError, TypeError, ValueError):
            return frozenset()


def _clear_history_caches() -> None:
    """清除行情快取；主要供測試及維運時主動失效使用。"""
    global _index_cache, _index_lock, _calendar_lock
    _stock_cache.clear()
    _stock_locks.clear()
    _index_cache = None
    _index_lock = asyncio.Lock()
    _calendar_lock = asyncio.Lock()


class StockHistoryProviderError(RuntimeError):
    """歷史行情供應商連線或格式錯誤。"""


OFFICIAL_HISTORY_MONTHS = 9
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
TWSE_INDEX_DAY_URL = "https://www.twse.com.tw/indicesReport/MI_5MINS_HIST"
TPEX_STOCK_DAY_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"


def _month_starts(count: int = OFFICIAL_HISTORY_MONTHS) -> list[date]:
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    result: list[date] = []
    year, month = today.year, today.month
    for _ in range(count):
        result.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return result


def _number(value: object) -> float:
    text = str(value).replace(",", "").strip()
    if not text or text in {"--", "---", "X"}:
        raise ValueError(f"無法解析行情數值：{value}")
    return float(text)


def _roc_date(value: object) -> date:
    year, month, day = (int(part) for part in str(value).strip().split("/"))
    return date(year + 1911, month, day)


def _parse_twse_stock(payload: dict) -> list[DailyBar]:
    if payload.get("stat") != "OK":
        return []
    result: list[DailyBar] = []
    for row in payload.get("data", []):
        try:
            result.append(
                DailyBar(
                    day=_roc_date(row[0]),
                    volume=_number(row[1]),
                    open=_number(row[3]),
                    high=_number(row[4]),
                    low=_number(row[5]),
                    close=_number(row[6]),
                )
            )
        except (IndexError, TypeError, ValueError):
            continue
    return result


def _parse_tpex_stock(payload: dict) -> list[DailyBar]:
    tables = payload.get("tables") or []
    rows = tables[0].get("data", []) if tables else []
    result: list[DailyBar] = []
    for row in rows:
        try:
            result.append(
                DailyBar(
                    day=_roc_date(row[0]),
                    volume=_number(row[1]),
                    open=_number(row[3]),
                    high=_number(row[4]),
                    low=_number(row[5]),
                    close=_number(row[6]),
                )
            )
        except (IndexError, TypeError, ValueError):
            continue
    return result


def _parse_twse_index(payload: dict) -> list[DailyBar]:
    if payload.get("stat") != "OK":
        return []
    result: list[DailyBar] = []
    for row in payload.get("data", []):
        try:
            result.append(
                DailyBar(
                    day=_roc_date(row[0]),
                    open=_number(row[1]),
                    high=_number(row[2]),
                    low=_number(row[3]),
                    close=_number(row[4]),
                    volume=0,
                )
            )
        except (IndexError, TypeError, ValueError):
            continue
    return result


async def _official_payload(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str],
) -> dict:
    response = await client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("交易所回應格式錯誤")
    return payload


def _official_http_options() -> tuple[dict[str, str], httpx.Limits]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "Warrants-Scoring/1.0 (+https://github.com/Qing04200420/Warrants)",
    }
    return headers, httpx.Limits(max_connections=4, max_keepalive_connections=4)


async def _stock_from_official_exchanges(code: str) -> _StockHistoryPart:
    import twstock

    item = twstock.codes.get(code)
    is_tpex = bool(item and item.data_source == "tpex")
    months = _month_starts()
    headers, limits = _official_http_options()
    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True, limits=limits) as client:
        if is_tpex:
            stock_requests = [
                _official_payload(
                    client,
                    TPEX_STOCK_DAY_URL,
                    {"code": code, "date": month.strftime("%Y/%m/%d"), "response": "json"},
                )
                for month in months
            ]
            stock_parser = _parse_tpex_stock
            market_name = "櫃買中心"
        else:
            stock_requests = [
                _official_payload(
                    client,
                    TWSE_STOCK_DAY_URL,
                    {"stockNo": code, "date": month.strftime("%Y%m%d"), "response": "json"},
                )
                for month in months
            ]
            stock_parser = _parse_twse_stock
            market_name = "臺灣證券交易所"

        stock_payloads = await asyncio.gather(*stock_requests, return_exceptions=True)

    stock_bars: list[DailyBar] = []
    for payload in stock_payloads:
        if isinstance(payload, dict):
            stock_bars.extend(stock_parser(payload))
    stock_bars = sorted({bar.day: bar for bar in stock_bars}.values(), key=lambda bar: bar.day)
    if not stock_bars:
        raise StockHistoryProviderError("交易所官方個股歷史行情服務暫時無法連線")

    return _StockHistoryPart(
        code=code,
        name=item.name if item else code,
        bars=stock_bars,
        source=f"{market_name}個股日成交資訊",
    )


async def _index_from_official_exchange() -> _IndexHistoryPart:
    months = _month_starts()
    headers, limits = _official_http_options()
    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True, limits=limits) as client:
        index_requests = [
            _official_payload(
                client,
                TWSE_INDEX_DAY_URL,
                {"date": month.strftime("%Y%m%d"), "response": "json"},
            )
            for month in months
        ]
        index_payloads = await asyncio.gather(*index_requests, return_exceptions=True)

    index_bars: list[DailyBar] = []
    for payload in index_payloads:
        if isinstance(payload, dict):
            index_bars.extend(_parse_twse_index(payload))
    index_bars = sorted({bar.day: bar for bar in index_bars}.values(), key=lambda bar: bar.day)
    if not index_bars:
        raise StockHistoryProviderError("交易所官方加權指數歷史行情服務暫時無法連線")

    return _IndexHistoryPart(
        bars=index_bars,
        source="臺灣證券交易所加權指數歷史資料",
    )


async def _from_official_exchanges(code: str) -> StockHistory:
    """相容舊介面的完整查詢；評分流程會分別快取個股與大盤。"""
    stock, index = await asyncio.gather(
        _stock_from_official_exchanges(code),
        _index_from_official_exchange(),
    )

    return StockHistory(
        code=stock.code,
        name=stock.name,
        bars=stock.bars,
        index_bars=index.bars,
        source=f"{stock.source} / {index.source}",
    )


def _daily_from_kbars(payloads: list[dict]) -> list[DailyBar]:
    grouped: dict[date, dict[str, float]] = {}
    for payload in payloads:
        timestamps = payload.get("datetime") or payload.get("ts") or []
        opens = payload.get("Open") or payload.get("open") or []
        highs = payload.get("High") or payload.get("high") or []
        lows = payload.get("Low") or payload.get("low") or []
        closes = payload.get("Close") or payload.get("close") or []
        volumes = payload.get("Volume") or payload.get("volume") or []
        for ts, open_, high, low, close, volume in zip(timestamps, opens, highs, lows, closes, volumes):
            if isinstance(ts, (int, float)):
                day = datetime.fromtimestamp(ts / 1_000_000_000, ZoneInfo("Asia/Taipei")).date()
            else:
                day = date.fromisoformat(str(ts)[:10])
            values = grouped.setdefault(
                day,
                {"open": float(open_), "high": float(high), "low": float(low), "close": float(close), "volume": 0.0},
            )
            values["high"] = max(values["high"], float(high))
            values["low"] = min(values["low"], float(low))
            values["close"] = float(close)
            values["volume"] += float(volume)
    return [DailyBar(day=day, **values) for day, values in sorted(grouped.items())]


async def _shioaji_range(
    client: ShioajiHttpClient,
    *,
    code: str,
    security_type: str,
    exchange: str,
    start: date,
    end: date,
) -> list[DailyBar]:
    payloads: list[dict] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=29), end)
        payloads.append(
            await client.kbars(
                code=code,
                security_type=security_type,
                exchange=exchange,
                start=cursor.isoformat(),
                end=chunk_end.isoformat(),
            )
        )
        cursor = chunk_end + timedelta(days=1)
    return _daily_from_kbars(payloads)


async def _stock_from_shioaji(code: str, client: ShioajiHttpClient) -> _StockHistoryPart:
    info = await client.contract_info(code)
    end = datetime.now(TAIPEI_TIMEZONE).date()
    start = end - timedelta(days=180)
    stock_bars = await _shioaji_range(
        client,
        code=code,
        security_type=str(info.get("security_type", "STK")),
        exchange=str(info.get("exchange", "TSE")),
        start=start,
        end=end,
    )
    if not stock_bars:
        raise StockHistoryProviderError("Shioaji 個股歷史行情沒有資料")

    return _StockHistoryPart(
        code=code,
        name=str(info.get("name") or code),
        bars=stock_bars,
        source="永豐金證券 Shioaji 個股 Kbars",
    )


async def _index_from_shioaji(client: ShioajiHttpClient) -> _IndexHistoryPart:
    end = datetime.now(TAIPEI_TIMEZONE).date()
    start = end - timedelta(days=180)
    index_bars = await _shioaji_range(
        client,
        code="IX0001",
        security_type="IND",
        exchange="TSE",
        start=start,
        end=end,
    )
    if not index_bars:
        raise StockHistoryProviderError("Shioaji 加權指數歷史行情沒有資料")

    return _IndexHistoryPart(
        bars=index_bars,
        source="永豐金證券 Shioaji 加權指數 Kbars",
    )


async def _from_shioaji(code: str, client: ShioajiHttpClient) -> StockHistory:
    """相容舊介面的完整查詢；評分流程會分別快取個股與大盤。"""
    stock, index = await asyncio.gather(
        _stock_from_shioaji(code, client),
        _index_from_shioaji(client),
    )
    return StockHistory(
        code=stock.code,
        name=stock.name,
        bars=stock.bars,
        index_bars=index.bars,
        source="永豐金證券 Shioaji Kbars",
    )


def _frame_to_bars(frame) -> list[DailyBar]:
    result: list[DailyBar] = []
    for stamp, row in frame.dropna(subset=["Open", "High", "Low", "Close"]).iterrows():
        result.append(
            DailyBar(
                day=stamp.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0) or 0),
            )
        )
    return result


def _stock_from_yfinance_sync(code: str) -> _StockHistoryPart:
    import twstock
    import yfinance as yf

    item = twstock.codes.get(code)
    # twstock 的 data_source 可直接辨識上市／上櫃，避免上櫃股票先查不存在的 .TW。
    # 即使靜態代碼表缺漏，仍保留另一市場作為第二順位。
    suffixes = (".TWO", ".TW") if item and item.data_source == "tpex" else (".TW", ".TWO")
    frame = None
    symbol = ""
    provider_errors: list[Exception] = []
    for suffix in suffixes:
        try:
            candidate = yf.Ticker(code + suffix).history(period="1y", interval="1d", auto_adjust=True)
        except Exception as exc:
            # 某些 yfinance/curl 版本會對不存在的市場後綴直接拋錯；
            # 單一候選失敗不應阻止系統繼續嘗試另一個市場。
            provider_errors.append(exc)
            continue
        if not candidate.empty:
            frame, symbol = candidate, code + suffix
            break
    if frame is None:
        if provider_errors and len(provider_errors) == len(suffixes):
            raise StockHistoryProviderError("Yahoo Finance 股票日線服務暫時無法連線") from provider_errors[-1]
        raise ValueError("查無股票歷史行情，請確認股票代號")

    return _StockHistoryPart(
        code=code,
        name=item.name if item else code,
        bars=_frame_to_bars(frame),
        source=f"Yahoo Finance 個股日線備援（{symbol}）",
        warning="目前未啟用 Shioaji，技術分析採 Yahoo Finance 日線備援。",
    )


def _index_from_yfinance_sync() -> _IndexHistoryPart:
    import yfinance as yf

    try:
        index_frame = yf.Ticker("^TWII").history(period="1y", interval="1d", auto_adjust=True)
    except Exception as exc:
        raise StockHistoryProviderError("Yahoo Finance 加權指數日線服務暫時無法連線") from exc
    if index_frame.empty:
        raise ValueError("查無加權指數歷史行情")
    return _IndexHistoryPart(
        bars=_frame_to_bars(index_frame),
        source="Yahoo Finance 加權指數日線備援（^TWII）",
    )


def _from_yfinance_sync(code: str) -> StockHistory:
    """相容舊介面的完整查詢；評分流程會分別快取個股與大盤。"""
    stock = _stock_from_yfinance_sync(code)
    index = _index_from_yfinance_sync()
    symbol = stock.source.removeprefix("Yahoo Finance 個股日線備援（").removesuffix("）")
    return StockHistory(
        code=stock.code,
        name=stock.name,
        bars=stock.bars,
        index_bars=index.bars,
        source=f"Yahoo Finance 日線備援（{symbol} / ^TWII）",
        warning=stock.warning,
    )


async def _load_stock_history_part(code: str, client: ShioajiHttpClient) -> _StockHistoryPart:
    if client.enabled:
        try:
            return await _stock_from_shioaji(code, client)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, StockHistoryProviderError):
            result = await _stock_from_official_exchanges(code)
            return _StockHistoryPart(
                **{**result.__dict__, "warning": "Shioaji 暫時無法使用，個股已改用交易所官方資料。"}
            )

    try:
        return await _stock_from_official_exchanges(code)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, StockHistoryProviderError):
        return await asyncio.to_thread(_stock_from_yfinance_sync, code)


async def _load_index_history_part(client: ShioajiHttpClient) -> _IndexHistoryPart:
    if client.enabled:
        try:
            return await _index_from_shioaji(client)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, StockHistoryProviderError):
            result = await _index_from_official_exchange()
            return _IndexHistoryPart(
                **{**result.__dict__, "warning": "Shioaji 暫時無法使用，大盤已改用交易所官方資料。"}
            )

    try:
        return await _index_from_official_exchange()
    except (httpx.HTTPError, KeyError, TypeError, ValueError, StockHistoryProviderError):
        return await asyncio.to_thread(_index_from_yfinance_sync)


async def _cached_stock_history(code: str, client: ShioajiHttpClient) -> _StockHistoryPart:
    now = datetime.now(TAIPEI_TIMEZONE)
    cached = _stock_cache.get(code)
    if _cache_is_valid(cached, now):
        return cached.value

    # 同一股票的併發 miss 只允許一個請求實際下載，其餘等待後共用結果。
    lock = _stock_locks.setdefault(code, asyncio.Lock())
    async with lock:
        now = datetime.now(TAIPEI_TIMEZONE)
        cached = _stock_cache.get(code)
        if _cache_is_valid(cached, now):
            return cached.value

        result, holidays = await asyncio.gather(
            _load_stock_history_part(code, client),
            _load_market_holidays(),
        )
        if len(result.bars) < 80:
            raise ValueError("歷史行情筆數不足，至少需要個股 80 日資料")
        completed_at = datetime.now(TAIPEI_TIMEZONE)
        _stock_cache[code] = _CacheEntry(result, _cache_expires_at(completed_at, holidays))
        return result


async def _cached_index_history(client: ShioajiHttpClient) -> _IndexHistoryPart:
    global _index_cache
    now = datetime.now(TAIPEI_TIMEZONE)
    if _cache_is_valid(_index_cache, now):
        return _index_cache.value

    # 大盤只有一個共享鍵；大量不同股票同時評分也只會下載一次。
    async with _index_lock:
        now = datetime.now(TAIPEI_TIMEZONE)
        if _cache_is_valid(_index_cache, now):
            return _index_cache.value

        result, holidays = await asyncio.gather(
            _load_index_history_part(client),
            _load_market_holidays(),
        )
        if len(result.bars) < 60:
            raise ValueError("歷史行情筆數不足，至少需要加權指數 60 日資料")
        completed_at = datetime.now(TAIPEI_TIMEZONE)
        _index_cache = _CacheEntry(result, _cache_expires_at(completed_at, holidays))
        return result


async def fetch_stock_history(code: str) -> StockHistory:
    client = ShioajiHttpClient()
    stock, index = await asyncio.gather(
        _cached_stock_history(code, client),
        _cached_index_history(client),
    )

    warnings = list(dict.fromkeys(item for item in (stock.warning, index.warning) if item))
    result = StockHistory(
        code=stock.code,
        name=stock.name,
        bars=stock.bars,
        index_bars=index.bars,
        source=f"{stock.source} / {index.source}",
        warning=" ".join(warnings) or None,
    )

    return result
