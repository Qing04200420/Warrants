"""Black-Scholes 權證估價；純函式方便 API 與測試共用。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import erf, exp, log, sqrt


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class PriceResult:
    theoretical_price: float
    intrinsic_value: float
    time_value: float
    delta: float


def trading_days_between(
    valuation_date: date,
    last_trading_date: date,
    holidays: set[date] | None = None,
) -> int:
    """計算評價日後至最後交易日（含）的交易日，排除週末及官方休市日。"""
    if valuation_date >= last_trading_date:
        return 0
    current = valuation_date + timedelta(days=1)
    count = 0
    closed = holidays or set()
    while current <= last_trading_date:
        if current.weekday() < 5 and current not in closed:
            count += 1
        current += timedelta(days=1)
    return count


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + erf(value / sqrt(2)))


def price_warrant(
    *,
    call_put: str,
    stock_price: float,
    strike_price: float,
    exercise_ratio: float,
    trading_days: int,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float = 0,
) -> PriceResult:
    """以年化參數估算歐式認購／認售權證每單位理論價。"""
    kind = call_put.upper()
    if kind not in {"C", "P"}:
        raise ValueError("權證類型必須為 C 或 P")
    if stock_price < 0 or strike_price <= 0 or exercise_ratio <= 0:
        raise ValueError("標的價格不得為負，履約價與行使比例必須大於 0")
    if trading_days < 0 or volatility < 0:
        raise ValueError("剩餘交易日與波動率不得為負")

    intrinsic_per_share = (
        max(stock_price - strike_price, 0)
        if kind == "C"
        else max(strike_price - stock_price, 0)
    )
    intrinsic = intrinsic_per_share * exercise_ratio
    if trading_days == 0 or volatility == 0 or stock_price == 0:
        return PriceResult(intrinsic, intrinsic, 0, 0)

    years = trading_days / TRADING_DAYS_PER_YEAR
    time_volatility = volatility * sqrt(years)
    d1 = (
        log(stock_price / strike_price)
        + (risk_free_rate - dividend_yield + volatility**2 / 2) * years
    ) / time_volatility
    d2 = d1 - time_volatility
    discounted_stock = stock_price * exp(-dividend_yield * years)
    discounted_strike = strike_price * exp(-risk_free_rate * years)

    if kind == "C":
        option_value = discounted_stock * _normal_cdf(d1) - discounted_strike * _normal_cdf(d2)
        delta = exp(-dividend_yield * years) * _normal_cdf(d1) * exercise_ratio
    else:
        option_value = discounted_strike * _normal_cdf(-d2) - discounted_stock * _normal_cdf(-d1)
        delta = -exp(-dividend_yield * years) * _normal_cdf(-d1) * exercise_ratio

    theoretical = max(option_value * exercise_ratio, intrinsic)
    return PriceResult(
        theoretical_price=theoretical,
        intrinsic_value=intrinsic,
        time_value=max(theoretical - intrinsic, 0),
        delta=delta,
    )
