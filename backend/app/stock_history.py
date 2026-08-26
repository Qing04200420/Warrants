"""股票與加權指數歷史日線；Shioaji 優先、Yahoo 僅作備援。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from time import monotonic
from zoneinfo import ZoneInfo

import httpx

from .broker import ShioajiHttpClient


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


CACHE_TTL_SECONDS = 15 * 60
_cache: dict[str, tuple[float, StockHistory]] = {}


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


async def _from_shioaji(code: str, client: ShioajiHttpClient) -> StockHistory:
    info = await client.contract_info(code)
    end = datetime.now(ZoneInfo("Asia/Taipei")).date()
    start = end - timedelta(days=180)
    stock_bars = await _shioaji_range(
        client,
        code=code,
        security_type=str(info.get("security_type", "STK")),
        exchange=str(info.get("exchange", "TSE")),
        start=start,
        end=end,
    )
    index_bars = await _shioaji_range(
        client,
        code="IX0001",
        security_type="IND",
        exchange="TSE",
        start=start,
        end=end,
    )
    return StockHistory(
        code=code,
        name=str(info.get("name") or code),
        bars=stock_bars,
        index_bars=index_bars,
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


def _from_yfinance_sync(code: str) -> StockHistory:
    import twstock
    import yfinance as yf

    frame = None
    symbol = ""
    for suffix in (".TW", ".TWO"):
        candidate = yf.Ticker(code + suffix).history(period="1y", interval="1d", auto_adjust=True)
        if not candidate.empty:
            frame, symbol = candidate, code + suffix
            break
    if frame is None:
        raise ValueError("查無股票歷史行情，請確認股票代號")
    index_frame = yf.Ticker("^TWII").history(period="1y", interval="1d", auto_adjust=True)
    if index_frame.empty:
        raise ValueError("查無加權指數歷史行情")
    item = twstock.codes.get(code)
    return StockHistory(
        code=code,
        name=item.name if item else code,
        bars=_frame_to_bars(frame),
        index_bars=_frame_to_bars(index_frame),
        source=f"Yahoo Finance 日線備援（{symbol} / ^TWII）",
        warning="目前未啟用 Shioaji，技術分析採 Yahoo Finance 日線備援。",
    )


async def fetch_stock_history(code: str) -> StockHistory:
    cached = _cache.get(code)
    now = monotonic()
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    client = ShioajiHttpClient()
    if client.enabled:
        try:
            result = await _from_shioaji(code, client)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            fallback = await asyncio.to_thread(_from_yfinance_sync, code)
            result = StockHistory(
                **{**fallback.__dict__, "warning": "Shioaji 歷史行情暫時無法取得，已切換 Yahoo Finance 日線備援。"}
            )
    else:
        result = await asyncio.to_thread(_from_yfinance_sync, code)

    if len(result.bars) < 80 or len(result.index_bars) < 60:
        raise ValueError("歷史行情筆數不足，至少需要個股 80 日與加權指數 60 日資料")
    _cache[code] = (now, result)
    return result
