"""永豐金證券 Shioaji HTTP API 的唯讀行情介面。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from time import monotonic
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class BrokerWarrant:
    underlying_code: str
    underlying_name: str
    name: str
    call_put: str
    strike_price: float
    exercise_ratio: float
    last_trading_date: str
    expiry_date: str
    exchange: str


@dataclass(frozen=True)
class BrokerSnapshot:
    code: str
    exchange: str
    close: float | None
    open: float | None
    high: float | None
    low: float | None
    total_volume: int | None
    bid: float | None
    ask: float | None
    quoted_at: str | None


_underlying_cache: tuple[float, list[dict]] | None = None


def _number(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_snapshot(row: dict) -> BrokerSnapshot:
    volume = _number(row.get("total_volume"))
    return BrokerSnapshot(
        code=str(row.get("code", "")),
        exchange=str(row.get("exchange", "TSE")),
        close=_number(row.get("close")),
        open=_number(row.get("open")),
        high=_number(row.get("high")),
        low=_number(row.get("low")),
        total_volume=int(volume) if volume is not None else None,
        bid=_number(row.get("buy_price")),
        ask=_number(row.get("sell_price")),
        quoted_at=row.get("datetime") or row.get("ts"),
    )


class ShioajiHttpClient:
    """連到使用者已登入的本機／內網 Shioaji server；不接觸交易端點。"""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("SHIOAJI_API_URL", "")).rstrip("/")
        if self.base_url:
            parsed = urlparse(self.base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("SHIOAJI_API_URL 必須是有效的 http(s) 網址")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def _get(self, path: str, params: dict | None = None):
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def find_warrant(self, code: str, underlying_name: str) -> BrokerWarrant | None:
        global _underlying_cache
        now = monotonic()
        if _underlying_cache is None or now - _underlying_cache[0] > 6 * 60 * 60:
            rows = await self._get(
                "/api/v1/data/contracts/warrants/underlyings",
                {"include_name": "true"},
            )
            _underlying_cache = (now, rows)
        normalized = underlying_name.replace("-KY", "").replace("KY", "")
        target = next(
            (
                row
                for row in _underlying_cache[1]
                if str(row.get("name", "")).replace("-KY", "").replace("KY", "") == normalized
            ),
            None,
        )
        if target is None:
            return None
        underlying_code = str(target["underlying_code"])
        warrants = await self._get(
            "/api/v1/data/contracts/warrants",
            {"underlying_code": underlying_code, "code": code.upper()},
        )
        row = next((item for item in warrants if str(item.get("code", "")).upper() == code.upper()), None)
        if row is None:
            return None
        return BrokerWarrant(
            underlying_code=underlying_code,
            underlying_name=str(target.get("name") or underlying_name),
            name=str(row.get("name", "")),
            call_put=str(row.get("call_put", "C")),
            strike_price=float(row["strike_price"]),
            exercise_ratio=float(row["exercise_ratio"]),
            last_trading_date=str(row["last_trading_date"]),
            expiry_date=str(row["expiry_date"]),
            exchange=str(row.get("exchange", "TSE")),
        )

    async def contract_info(self, code: str) -> dict:
        return await self._get(f"/api/v1/data/contracts/{code}/info")

    async def snapshot(self, *, code: str, security_type: str, exchange: str) -> BrokerSnapshot | None:
        payload = {"contracts": [{"security_type": security_type, "exchange": exchange, "code": code}]}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20) as client:
            response = await client.post("/api/v1/data/snapshots", json=payload)
            response.raise_for_status()
            rows = response.json()
        return parse_snapshot(rows[0]) if rows else None

    async def kbars(
        self,
        *,
        code: str,
        security_type: str,
        exchange: str,
        start: str,
        end: str,
    ) -> dict:
        """查詢最多 30 天的分鐘 K 線；呼叫端負責分段與彙整。"""
        payload = {
            "contract": {
                "security_type": security_type,
                "exchange": exchange,
                "code": code,
            },
            "start": start,
            "end": end,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.post("/api/v1/data/kbars", json=payload)
            response.raise_for_status()
            return response.json()
