"""依官方基本條款為多頭標的挑選認購權證候選名單。"""

from __future__ import annotations

from datetime import date
import re

from .models import WarrantRecommendation
from .twse_openapi import OfficialWarrant


def _normalized_name(value: str) -> str:
    return re.sub(r"[\s()（）-]", "", value).replace("KY", "").upper()


def _term_score(days: int) -> float:
    if 75 <= days <= 180:
        return 35.0
    if 45 <= days <= 240:
        return 27.0
    return 16.0


def _strike_score(gap_percent: float) -> float:
    distance = abs(gap_percent)
    if distance <= 5:
        return 50.0
    if distance <= 10:
        return 40.0
    if distance <= 20:
        return 24.0
    return 8.0


def recommend_warrants(
    warrants: list[OfficialWarrant],
    *,
    underlying_name: str,
    stock_price: float,
    as_of: date | None = None,
    limit: int = 5,
) -> list[WarrantRecommendation]:
    """優先挑選距到期至少 45 天、履約價在現價正負 15% 的認購權證。"""
    today = as_of or date.today()
    target_name = _normalized_name(underlying_name)
    candidates: list[tuple[OfficialWarrant, int, float]] = []
    for item in warrants:
        days = (item.last_trading_date - today).days
        if item.call_put != "C" or days < 30 or _normalized_name(item.underlying_name) != target_name:
            continue
        gap_percent = (item.strike_price - stock_price) / stock_price * 100
        if abs(gap_percent) > 20:
            continue
        candidates.append((item, days, gap_percent))

    # 先採條件較穩健的區間；不足時再用其他仍有至少 30 天的認購權證補齊。
    rank_key = lambda row: (abs(row[2]), abs(row[1] - 120), -row[0].exercise_ratio, row[0].code)
    preferred = sorted((row for row in candidates if row[1] >= 45 and abs(row[2]) <= 15), key=rank_key)
    preferred_codes = {row[0].code for row in preferred}
    fallback = sorted((row for row in candidates if row[0].code not in preferred_codes), key=rank_key)
    pool = preferred + fallback

    result: list[WarrantRecommendation] = []
    for item, days, gap_percent in pool[:limit]:
        moneyness = "價外" if gap_percent > 0.5 else "價內" if gap_percent < -0.5 else "價平"
        score = min(99.0, _strike_score(gap_percent) + _term_score(days) + (10.0 if item.exercise_ratio > 0 else 0.0))
        result.append(
            WarrantRecommendation(
                code=item.code,
                name=item.name,
                strike_price=item.strike_price,
                exercise_ratio=item.exercise_ratio,
                last_trading_date=item.last_trading_date.isoformat(),
                expiry_date=item.expiry_date.isoformat(),
                days_to_last_trading=days,
                moneyness=moneyness,
                strike_gap_percent=round(gap_percent, 2),
                match_score=round(score, 1),
                reason=f"履約價接近現價（{moneyness} {abs(gap_percent):.1f}%），距最後交易 {days} 天",
            )
        )
    return result
