"""Adapter for a gateway hosting the official Yuanta SPARK native SDK."""

from __future__ import annotations

import os
import httpx

from .models import StockQuote


class YuantaNotConfigured(RuntimeError):
    pass


async def fetch_yuanta_quote(code: str, name: str = "") -> StockQuote:
    base_url = os.getenv("YUANTA_GATEWAY_URL", "").rstrip("/")
    if not base_url:
        raise YuantaNotConfigured("YUANTA_GATEWAY_URL is not configured")
    headers = {}
    if token := os.getenv("YUANTA_GATEWAY_TOKEN", ""):
        headers["Authorization"] = f"Bearer {token}"
    timeout = float(os.getenv("YUANTA_GATEWAY_TIMEOUT", "2.5"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"{base_url}/v1/quotes/{code}", headers=headers)
        response.raise_for_status()
        payload = response.json()

    def number(key: str) -> float | None:
        value = payload.get(key)
        return None if value in (None, "", "-") else float(value)

    volume = payload.get("volume")
    return StockQuote(
        code=code, name=payload.get("name") or name,
        price=number("price"), open=number("open"), high=number("high"), low=number("low"),
        volume=None if volume in (None, "", "-") else int(float(volume)),
        source="元大證券 SPARK API", quoted_at=payload.get("quoted_at"),
    )
