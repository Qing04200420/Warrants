from .models import ScoreItem, WarrantMetrics


def _band(value: float, bands: list[tuple[float, float]]) -> float:
    """依數值落入的第一個上限區間回傳分數。"""
    for threshold, points in bands:
        if value <= threshold:
            return points
    return bands[-1][1]


def calculate_score(m: WarrantMetrics) -> tuple[float, str, list[ScoreItem]]:
    """套用淘汰條件與十項權重，回傳總分、評級及逐項說明。"""
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
        # 缺值採中性分，避免把「沒有資料」錯當成 0% 的優良 IV。
        iv_score = 7.5
        iv_note = "資料缺失，採中性分"
    else:
        iv = m.implied_vol
        iv_score = _band(iv, [(0.2, 15), (0.35, 12), (0.6, 8), (1.0, 4), (999, 1)])
        iv_note = f"隱含波動率 {iv:.2%}"

    # 2) 隱含波動率穩定度 (10) - 低波動越好
    if m.iv_std is None:
        # 累積歷史不足時仍可評分，但會在說明中清楚標示資料缺失。
        ivs_score = 5.0
        ivs_note = "資料缺失，採中性分"
    else:
        ivs_score = _band(m.iv_std, [(0.02, 10), (0.05, 8), (0.1, 6), (0.2, 3), (999, 1)])
        if m.iv_std_source == "twse_14d_max_change_proxy":
            ivs_note = f"TWSE 14 日委買 IV 最大變動 {m.iv_std:.2%}（暫代穩定度）"
        else:
            count = f"（{m.iv_history_count} 筆盤後資料）" if m.iv_history_count else ""
            ivs_note = f"14 日委買 IV 標準差 {m.iv_std:.2%}{count}"

    # 3) 買賣價差與掛單量 (15) - 結合 spread 與委託量
    # 價差與掛單量各自評分後取平均，共占 15 分。
    spread_score = 7.5
    vol_score = 7.5
    if m.bid_ask_spread is not None:
        spread_score = _band(m.bid_ask_spread, [(0.01, 15), (0.03, 12), (0.05, 8), (0.1, 4), (999, 1)])
    volume_available = (m.bid_volume is not None) or (m.ask_volume is not None)
    total_vol = None
    if volume_available:
        total_vol = sum(volume for volume in (m.bid_volume, m.ask_volume) if volume is not None)
        vol_score = _band(total_vol, [(100, 2), (500, 8), (2000, 12), (10000, 15), (9999999, 15)])
    liquidity_score = round((spread_score + vol_score) / 2, 1)
    liquidity_notes = []
    if m.bid_ask_spread is None:
        liquidity_notes.append("買賣價差資料缺失（採中性分）")
    else:
        liquidity_notes.append(f"買賣價差 {m.bid_ask_spread:.4f}")
    if total_vol is None:
        liquidity_notes.append("掛單量資料缺失（採中性分）")
    else:
        liquidity_notes.append(f"總掛單量 {total_vol}")
    liquidity_note = "；".join(liquidity_notes)

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

    # 統一在此組裝前端評分拆解需要的 key、名稱、得分與說明。
    values = [
        ("iv_reasonable", "隱含波動率合理性", iv_score, 15, iv_note),
        ("iv_stability", "隱含波動率穩定度", ivs_score, 10, ivs_note),
        ("liquidity", "買賣價差與掛單量", liquidity_score, 15, liquidity_note),
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
