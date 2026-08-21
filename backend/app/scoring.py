from .models import ScoreItem, WarrantMetrics


def _band(value: float, bands: list[tuple[float, float]]) -> float:
    for threshold, points in bands:
        if value <= threshold:
            return points
    return bands[-1][1]


def calculate_score(m: WarrantMetrics) -> tuple[float, str, list[ScoreItem]]:
    # 淘汰機制：剩餘天數過短或委買量過少直接淘汰
    if m.days_to_expiry < 30:
        items = [ScoreItem(key="eliminated", label="淘汰：剩餘天數不足", score=0, max_score=100, note=f"剩餘 {m.days_to_expiry} 天 < 30 天")]
        return 0.0, "淘汰", items
    if m.bid_volume is not None and m.bid_volume < 50:
        items = [ScoreItem(key="eliminated", label="淘汰：委買量過少", score=0, max_score=100, note=f"委買量 {m.bid_volume} < 50")]
        return 0.0, "淘汰", items

    # 新權重配比，總分 100
    # 1) 隱含波動率合理性 (15)
    if m.implied_vol is None:
        iv_score = 7.5
    else:
        iv = m.implied_vol
        iv_score = _band(iv, [(0.2, 15), (0.35, 12), (0.6, 8), (1.0, 4), (999, 1)])

    # 2) 隱含波動率穩定度 (10) - 低波動越好
    if m.iv_std is None:
        ivs_score = 5.0
    else:
        ivs_score = _band(m.iv_std, [(0.02, 10), (0.05, 8), (0.1, 6), (0.2, 3), (999, 1)])

    # 3) 買賣價差與掛單量 (15) - 結合 spread 與委託量
    spread_score = 7.5
    vol_score = 7.5
    if m.bid_ask_spread is not None:
        spread_score = _band(m.bid_ask_spread, [(0.01, 15), (0.03, 12), (0.05, 8), (0.1, 4), (999, 1)])
    if (m.bid_volume is not None) or (m.ask_volume is not None):
        total_vol = (m.bid_volume or 0) + (m.ask_volume or 0)
        vol_score = _band(total_vol, [(100, 2), (500, 8), (2000, 12), (10000, 15), (9999999, 15)])
    liquidity_score = round((spread_score + vol_score) / 2, 1)

    # 4) 有效槓桿 (12)
    leverage = _band(abs(m.effective_leverage), [(2, 12), (5, 10), (10, 8), (15, 5), (999, 2)])

    # 5) 價內外程度 (10)
    out = abs(m.moneyness_percent)
    money = _band(out, [(3, 10), (8, 8), (15, 6), (25, 3), (999, 1)])

    # 6) Delta (8)
    delta_abs = abs(m.delta)
    delta = _band(delta_abs, [(0.1, 2), (0.2, 5), (0.35, 7), (0.65, 8), (99, 6)])

    # 7) 距到期日 (8)
    days = _band(m.days_to_expiry, [(30, 2), (60, 5), (120, 7), (180, 8), (99999, 6)])

    # 8) 執行比例 (8)
    ratio = _band(m.exercise_ratio, [(0.01, 2), (0.05, 5), (0.2, 8), (0.5, 6), (999, 3)])

    # 9) Theta 損耗 (7)
    theta_ratio = abs(m.theta) / max(m.warrant_price, 0.01) * 100
    theta = _band(theta_ratio, [(0.5, 7), (1, 5), (2, 3), (4, 1), (999, 1)])

    # 10) 價格合理性／溢價率 (7)
    strike_gap = abs(m.strike_price * m.exercise_ratio - m.warrant_price)
    price_quality = 7 if strike_gap >= 0 else 3

    values = [
        ("iv_reasonable", "隱含波動率合理性", iv_score, 15, f"implied_vol={m.implied_vol}"),
        ("iv_stability", "隱含波動率穩定度", ivs_score, 10, f"iv_std={m.iv_std}"),
        ("liquidity", "買賣價差與掛單量", liquidity_score, 15, f"spread={m.bid_ask_spread} vol={(m.bid_volume or 0)+(m.ask_volume or 0)}"),
        ("leverage", "有效槓桿", leverage, 12, f"{m.effective_leverage:.2f} 倍"),
        ("moneyness", "價內外程度", money, 10, f"{m.moneyness_percent:.2f}% {m.moneyness_label}"),
        ("delta", "Delta", delta, 8, f"Delta {m.delta:.4f}"),
        ("days", "距到期日", days, 8, f"剩餘 {m.days_to_expiry} 天"),
        ("ratio", "執行比例", ratio, 8, f"{m.exercise_ratio:.4f}"),
        ("theta", "Theta 損耗", theta, 7, f"每日約占權證價 {theta_ratio:.2f}%"),
        ("price", "價格合理性/溢價率", price_quality, 7, f"履約價 {m.strike_price:.2f}"),
    ]
    items = [ScoreItem(key=k, label=l, score=s, max_score=mx, note=n) for k, l, s, mx, n in values]
    total = round(sum(item.score for item in items), 1)
    rating = "優良" if total >= 80 else "良好" if total >= 65 else "普通" if total >= 50 else "偏弱"
    return total, rating, items

