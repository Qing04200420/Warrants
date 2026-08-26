"""股票標的多頭技術面評分。所有規則與權重集中於此。"""

from __future__ import annotations

from collections.abc import Sequence

from .models import StockScoreItem, StockScoreRequest, StockScoreResponse
from .stock_history import DailyBar, StockHistory


def _sma(values: Sequence[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"計算 MA{period} 的資料不足")
    return sum(values[-period:]) / period


def _ema_series(values: Sequence[float], period: int) -> list[float]:
    multiplier = 2 / (period + 1)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(float(value) * multiplier + result[-1] * (1 - multiplier))
    return result


def _rsi(values: Sequence[float], period: int = 14) -> float:
    changes = [current - previous for previous, current in zip(values[-period - 1 : -1], values[-period:])]
    gain = sum(max(change, 0) for change in changes) / period
    loss = sum(max(-change, 0) for change in changes) / period
    if loss == 0:
        return 100.0
    return 100 - 100 / (1 + gain / loss)


def _macd(values: Sequence[float]) -> tuple[float, float, float]:
    fast = _ema_series(values, 12)
    slow = _ema_series(values, 26)
    line = [left - right for left, right in zip(fast, slow)]
    signal = _ema_series(line, 9)
    return line[-1], signal[-1], line[-1] - signal[-1]


def _kd(bars: Sequence[DailyBar], period: int = 9) -> tuple[float, float]:
    k = d = 50.0
    for index in range(period - 1, len(bars)):
        window = bars[index - period + 1 : index + 1]
        highest = max(bar.high for bar in window)
        lowest = min(bar.low for bar in window)
        rsv = 50.0 if highest == lowest else (bars[index].close - lowest) / (highest - lowest) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
    return k, d


def _weekly_bars(bars: Sequence[DailyBar]) -> list[DailyBar]:
    grouped: dict[tuple[int, int], list[DailyBar]] = {}
    for bar in bars:
        iso = bar.day.isocalendar()
        grouped.setdefault((iso.year, iso.week), []).append(bar)
    result: list[DailyBar] = []
    for rows in grouped.values():
        result.append(
            DailyBar(
                day=rows[-1].day,
                open=rows[0].open,
                high=max(row.high for row in rows),
                low=min(row.low for row in rows),
                close=rows[-1].close,
                volume=sum(row.volume for row in rows),
            )
        )
    return result


def _latest_swings(bars: Sequence[DailyBar], window: int = 2) -> tuple[float, float, float, float, str]:
    highs: list[float] = []
    lows: list[float] = []
    for index in range(window, len(bars) - window):
        nearby = bars[index - window : index + window + 1]
        if bars[index].high == max(item.high for item in nearby):
            highs.append(bars[index].high)
        if bars[index].low == min(item.low for item in nearby):
            lows.append(bars[index].low)
    if len(highs) >= 2 and len(lows) >= 2:
        return highs[-2], highs[-1], lows[-2], lows[-1], "近端轉折點"

    recent = list(bars[-20:])
    midpoint = len(recent) // 2
    return (
        max(item.high for item in recent[:midpoint]),
        max(item.high for item in recent[midpoint:]),
        min(item.low for item in recent[:midpoint]),
        min(item.low for item in recent[midpoint:]),
        "近 20 日前後半段",
    )


def calculate_stock_score(history: StockHistory, request: StockScoreRequest) -> StockScoreResponse:
    bars = history.bars
    index_bars = history.index_bars
    closes = [bar.close for bar in bars]
    index_closes = [bar.close for bar in index_bars]
    current = bars[-1]
    previous = bars[-2]
    items: list[StockScoreItem] = []

    def add(group: str, key: str, label: str, condition: bool, points: float, note: str, score: float | None = None):
        earned = points if condition else 0.0
        if score is not None:
            earned = score
        items.append(
            StockScoreItem(
                group=group,
                key=key,
                label=label,
                score=earned,
                max_score=points,
                passed=condition,
                note=note,
            )
        )

    # 大盤環境（10 分）
    index_close = index_closes[-1]
    index_ma20 = _sma(index_closes, 20)
    index_ma60 = _sma(index_closes, 60)
    add("大盤環境", "index_ma20", "加權指數站上 MA20", index_close > index_ma20, 5, f"指數 {index_close:.2f}／MA20 {index_ma20:.2f}")
    add("大盤環境", "index_ma60", "加權指數站上 MA60", index_close > index_ma60, 5, f"指數 {index_close:.2f}／MA60 {index_ma60:.2f}")

    # 日線趨勢（25 分）
    ma5, ma20, ma60 = _sma(closes, 5), _sma(closes, 20), _sma(closes, 60)
    ma20_five_days_ago = sum(closes[-25:-5]) / 20
    price_above_5, price_above_20, price_above_60 = current.close > ma5, current.close > ma20, current.close > ma60
    ma5_above_20, ma20_above_60 = ma5 > ma20, ma20 > ma60
    ma20_rising = ma20 > ma20_five_days_ago
    ideal = current.close > ma5 > ma20 > ma60
    add("日線趨勢", "price_ma5", "股價高於 MA5", price_above_5, 2, f"收盤 {current.close:.2f}／MA5 {ma5:.2f}")
    add("日線趨勢", "price_ma20", "股價高於 MA20", price_above_20, 2, f"收盤 {current.close:.2f}／MA20 {ma20:.2f}")
    add("日線趨勢", "price_ma60", "股價高於 MA60", price_above_60, 2, f"收盤 {current.close:.2f}／MA60 {ma60:.2f}")
    add("日線趨勢", "ma5_ma20", "MA5 高於 MA20", ma5_above_20, 4, f"MA5 {ma5:.2f}／MA20 {ma20:.2f}")
    add("日線趨勢", "ma20_ma60", "MA20 高於 MA60", ma20_above_60, 4, f"MA20 {ma20:.2f}／MA60 {ma60:.2f}")
    add("日線趨勢", "ma20_rising", "MA20 向上", ma20_rising, 5, f"目前 {ma20:.2f}／5 日前 {ma20_five_days_ago:.2f}")
    add("日線趨勢", "ideal_order", "股價 > MA5 > MA20 > MA60", ideal, 6, "理想多頭排列" if ideal else "尚未形成完整多頭排列")

    # 週線趨勢（10 分）
    weekly_bars = _weekly_bars(bars)
    weekly_closes = [bar.close for bar in weekly_bars]
    if len(weekly_closes) < 14:
        raise ValueError("週線資料不足，至少需要 14 週")
    weekly_close = weekly_closes[-1]
    weekly_ma5, weekly_ma13 = _sma(weekly_closes, 5), _sma(weekly_closes, 13)
    weekly_ma5_previous = sum(weekly_closes[-6:-1]) / 5
    weekly_close_above = weekly_close > weekly_ma5
    weekly_order = weekly_ma5 > weekly_ma13
    weekly_rising = weekly_ma5 > weekly_ma5_previous
    add("週線趨勢", "weekly_price_ma5", "週收盤高於週 MA5", weekly_close_above, 3, f"週收盤 {weekly_close:.2f}／週 MA5 {weekly_ma5:.2f}")
    add("週線趨勢", "weekly_ma5_ma13", "週 MA5 高於週 MA13", weekly_order, 3, f"週 MA5 {weekly_ma5:.2f}／週 MA13 {weekly_ma13:.2f}")
    add("週線趨勢", "weekly_ma5_rising", "週 MA5 向上", weekly_rising, 4, f"目前 {weekly_ma5:.2f}／上週 {weekly_ma5_previous:.2f}")
    weekly_bullish = weekly_close_above and weekly_order and weekly_rising

    # 價格結構（10 分）
    prior_high, latest_high, prior_low, latest_low, structure_source = _latest_swings(bars[-80:])
    higher_high, higher_low = latest_high > prior_high, latest_low > prior_low
    add("價格結構", "higher_high", "新高高於前高", higher_high, 5, f"前高 {prior_high:.2f}／新高 {latest_high:.2f}（{structure_source}）")
    add("價格結構", "higher_low", "新低高於前低", higher_low, 5, f"前低 {prior_low:.2f}／新低 {latest_low:.2f}（{structure_source}）")

    # 量價關係（10 分）
    average_volume20 = sum(bar.volume for bar in bars[-21:-1]) / 20
    volume_ratio = current.volume / average_volume20 if average_volume20 else 0
    up_volumes = [bar.volume for before, bar in zip(bars[-21:-1], bars[-20:]) if bar.close >= before.close]
    down_volumes = [bar.volume for before, bar in zip(bars[-21:-1], bars[-20:]) if bar.close < before.close]
    up_average = sum(up_volumes) / len(up_volumes) if up_volumes else 0
    down_average = sum(down_volumes) / len(down_volumes) if down_volumes else 0
    if current.close > previous.close and volume_ratio >= 1.2:
        volume_score, volume_passed, volume_label = 10.0, True, "價漲量增"
    elif current.close > ma20 and up_average > down_average:
        volume_score, volume_passed, volume_label = 8.0, True, "上漲日量能優於下跌日"
    elif current.close > ma20 and 0.7 <= volume_ratio <= 1.5:
        volume_score, volume_passed, volume_label = 6.0, True, "量能中性且價格守穩 MA20"
    elif current.close < previous.close and volume_ratio >= 1.2:
        volume_score, volume_passed, volume_label = 0.0, False, "價跌量增"
    else:
        volume_score, volume_passed, volume_label = 3.0, False, "量價尚未明確確認"
    add("量價關係", "price_volume", "量價配合", volume_passed, 10, f"{volume_label}；量比 {volume_ratio:.2f}", volume_score)

    # 動能（15 分）
    rsi = _rsi(closes)
    if 50 <= rsi <= 70:
        rsi_score, rsi_passed = 5.0, True
    elif 40 <= rsi < 50 or 70 < rsi <= 80:
        rsi_score, rsi_passed = 2.0, False
    else:
        rsi_score, rsi_passed = 0.0, False
    add("動能指標", "rsi", "RSI 位於健康多頭區", rsi_passed, 5, f"RSI(14) {rsi:.2f}", rsi_score)

    macd_line, macd_signal, macd_histogram = _macd(closes)
    macd_bullish = macd_line > macd_signal and macd_histogram > 0
    add("動能指標", "macd", "MACD 多頭", macd_bullish, 5, f"MACD {macd_line:.3f}／Signal {macd_signal:.3f}／柱 {macd_histogram:.3f}")

    k_value, d_value = _kd(bars)
    kd_bullish = k_value > d_value and 20 <= k_value <= 80
    kd_score = 5.0 if kd_bullish else (2.0 if k_value > d_value else 0.0)
    add("動能指標", "kd", "KD 黃金交叉且未過熱", kd_bullish, 5, f"K {k_value:.2f}／D {d_value:.2f}", kd_score)

    # 風險報酬（20 分）
    risk = request.entry_price - request.stop_loss_price
    reward = request.target_price - request.entry_price
    ratio = reward / risk
    if ratio >= 3:
        rr_score = 20.0
    elif ratio >= 2:
        rr_score = 15.0
    elif ratio >= 1.5:
        rr_score = 10.0
    elif ratio >= 1:
        rr_score = 5.0
    else:
        rr_score = 0.0
    add("風險報酬", "risk_reward", "預期報酬／承擔風險", ratio >= 2, 20, f"風險 {risk:.2f}／報酬 {reward:.2f}／風報比 {ratio:.2f}", rr_score)

    score = round(sum(item.score for item in items), 1)
    if score >= 80:
        rating = "強勢多頭"
    elif score >= 65:
        rating = "偏多"
    elif score >= 50:
        rating = "中性觀察"
    else:
        rating = "趨勢偏弱"

    if ideal and weekly_bullish:
        summary = "日線與週線同步向上，屬較完整的多頭排列。"
    elif ideal and not weekly_bullish:
        summary = "日線強但週線尚未同步，需提防空頭反彈。"
    elif weekly_bullish:
        summary = "週線偏多，但日線尚未形成理想排列，宜等待短線確認。"
    else:
        summary = "日線與週線尚未同步轉強，認購權證條件較不完整。"

    return StockScoreResponse(
        code=history.code,
        name=history.name,
        as_of=current.day.isoformat(),
        close=current.close,
        score=score,
        rating=rating,
        summary=summary,
        market={"index_close": index_close, "ma20": index_ma20, "ma60": index_ma60, "above_ma20": index_close > index_ma20, "above_ma60": index_close > index_ma60},
        daily={"close": current.close, "ma5": ma5, "ma20": ma20, "ma60": ma60, "ma20_five_days_ago": ma20_five_days_ago, "ideal_order": ideal},
        weekly={"close": weekly_close, "ma5": weekly_ma5, "ma13": weekly_ma13, "ma5_previous": weekly_ma5_previous, "bullish": weekly_bullish},
        price_structure={"prior_high": prior_high, "latest_high": latest_high, "prior_low": prior_low, "latest_low": latest_low, "higher_high": higher_high, "higher_low": higher_low, "method": structure_source},
        volume={"current": current.volume, "average20": average_volume20, "ratio": volume_ratio, "up_day_average": up_average, "down_day_average": down_average, "assessment": volume_label},
        momentum={"rsi14": rsi, "macd": macd_line, "macd_signal": macd_signal, "macd_histogram": macd_histogram, "k": k_value, "d": d_value},
        risk_reward={"entry": request.entry_price, "stop_loss": request.stop_loss_price, "target": request.target_price, "risk": risk, "reward": reward, "ratio": ratio},
        items=items,
        source=history.source,
        warning=history.warning,
    )
