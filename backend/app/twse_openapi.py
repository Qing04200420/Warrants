"""TWSE OpenAPI 上市權證基本條款查詢。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from time import monotonic

import httpx


OPENAPI_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap37_L"
HOLIDAY_URL = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
CACHE_TTL_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class OfficialWarrant:
    code: str
    name: str
    call_put: str
    underlying_name: str
    strike_price: float
    exercise_ratio: float
    last_trading_date: date
    expiry_date: date
    data_date: date


_cache: tuple[float, dict[str, OfficialWarrant]] | None = None
_holiday_cache: tuple[float, set[date]] | None = None


def parse_roc_date(value: str) -> date:
    cleaned = value.strip().replace("/", "").replace("-", "")
    if len(cleaned) != 7 or not cleaned.isdigit():
        raise ValueError(f"無法解析民國日期：{value}")
    return date(int(cleaned[:3]) + 1911, int(cleaned[3:5]), int(cleaned[5:7]))


def parse_warrant_records(records: list[dict[str, str]]) -> dict[str, OfficialWarrant]:
    result: dict[str, OfficialWarrant] = {}
    for row in records:
        code = row.get("權證代號", "").strip().upper()
        if len(code) != 6:
            continue
        try:
            # 官方欄位是「每仟單位權證可履約的標的數量」，需除以 1000。
            exercise_ratio = float(row["最新標的履約配發數量(每仟單位權證)"]) / 1000
            result[code] = OfficialWarrant(
                code=code,
                name=row["權證簡稱"].strip(),
                call_put="P" if "售" in row.get("權證類型", "") else "C",
                underlying_name=row["標的證券/指數"].strip(),
                strike_price=float(row["最新履約價格(元)/履約指數"]),
                exercise_ratio=exercise_ratio,
                last_trading_date=parse_roc_date(row["最後交易日"]),
                expiry_date=parse_roc_date(row["履約截止日"]),
                data_date=parse_roc_date(row["出表日期"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return result


async def fetch_official_warrant(code: str) -> OfficialWarrant:
    global _cache
    now = monotonic()
    if _cache is None or now - _cache[0] >= CACHE_TTL_SECONDS:
        async with httpx.AsyncClient(timeout=45, headers={"User-Agent": "WarrantLab/2.0"}) as client:
            response = await client.get(OPENAPI_URL)
            response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("TWSE OpenAPI 回傳格式不正確")
        _cache = (now, parse_warrant_records(payload))

    item = _cache[1].get(code.upper())
    if item is None:
        raise ValueError("證交所查無此權證，請確認代號或是否已下市")
    return item


def parse_holiday_records(records: list[dict[str, str]]) -> set[date]:
    """端點同時含年初／年後開始交易日，僅保留真正沒有交易的日期。"""
    holidays: set[date] = set()
    for row in records:
        name = str(row.get("Name", ""))
        if "開始交易日" in name or "最後交易日" in name:
            continue
        try:
            value = parse_roc_date(str(row["Date"]))
        except (KeyError, ValueError):
            continue
        if value.weekday() < 5:
            holidays.add(value)
    return holidays


async def fetch_market_holidays() -> set[date]:
    global _holiday_cache
    now = monotonic()
    if _holiday_cache is None or now - _holiday_cache[0] >= CACHE_TTL_SECONDS:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "WarrantLab/2.0"}) as client:
            response = await client.get(HOLIDAY_URL)
            response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("TWSE 休市日 API 回傳格式不正確")
        _holiday_cache = (now, parse_holiday_records(payload))
    return _holiday_cache[1]
