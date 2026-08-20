from .models import ScoreItem, WarrantMetrics


def _band(value: float, bands: list[tuple[float, float]]) -> float:
    for threshold, points in bands:
        if value <= threshold:
            return points
    return bands[-1][1]


def calculate_score(m: WarrantMetrics) -> tuple[float, str, list[ScoreItem]]:
    # 分數衡量「交易條件均衡度」：避免過短到期、極價外、低 Delta 與過度槓桿。
    days = _band(m.days_to_expiry, [(14, 2), (30, 7), (60, 13), (120, 18), (180, 15), (99999, 10)])
    delta_abs = abs(m.delta)
    delta = _band(delta_abs, [(0.1, 2), (0.2, 6), (0.35, 12), (0.65, 16), (0.8, 13), (99, 9)])
    out = abs(m.moneyness_percent)
    money = _band(out, [(3, 16), (8, 13), (15, 9), (25, 4), (999, 1)])
    leverage = _band(abs(m.effective_leverage), [(2, 6), (5, 14), (10, 12), (15, 7), (999, 3)])
    theta_ratio = abs(m.theta) / max(m.warrant_price, 0.01) * 100
    theta = _band(theta_ratio, [(0.5, 14), (1, 11), (2, 7), (4, 3), (999, 1)])
    liquidity_proxy = _band(m.warrant_price, [(0.2, 2), (0.5, 5), (2, 10), (5, 8), (999, 5)])
    ratio = _band(m.exercise_ratio, [(0.01, 2), (0.05, 5), (0.2, 8), (0.5, 7), (999, 4)])
    strike_gap = abs(m.strike_price * m.exercise_ratio - m.warrant_price)
    price_quality = 4 if strike_gap >= 0 else 2

    values = [
        ("days", "距到期日", days, 18, f"剩餘 {m.days_to_expiry} 天"),
        ("delta", "Delta", delta, 16, f"Delta {m.delta:.4f}"),
        ("moneyness", "價內外程度", money, 16, f"{m.moneyness_percent:.2f}% {m.moneyness_label}"),
        ("leverage", "有效槓桿", leverage, 14, f"{m.effective_leverage:.2f} 倍"),
        ("theta", "Theta 損耗", theta, 14, f"每日約占權證價 {theta_ratio:.2f}%"),
        ("warrant_price", "權證價格", liquidity_proxy, 10, f"{m.warrant_price:.2f} 元"),
        ("ratio", "執行比例", ratio, 8, f"{m.exercise_ratio:.4f}"),
        ("strike", "履約價合理性", price_quality, 4, f"履約價 {m.strike_price:.2f}"),
    ]
    items = [ScoreItem(key=k, label=l, score=s, max_score=mx, note=n) for k, l, s, mx, n in values]
    total = round(sum(item.score for item in items), 1)
    rating = "優良" if total >= 80 else "良好" if total >= 65 else "普通" if total >= 50 else "偏弱"
    return total, rating, items

