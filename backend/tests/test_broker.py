from app.broker import parse_snapshot


def test_parses_shioaji_snapshot_fields():
    item = parse_snapshot({
        "datetime": "2026-08-24T13:30:00",
        "code": "2330",
        "exchange": "TSE",
        "open": 1200,
        "high": 1220,
        "low": 1190,
        "close": 1215,
        "total_volume": 10000,
        "buy_price": 1210,
        "sell_price": 1215,
    })

    assert item.close == 1215
    assert item.total_volume == 10000
    assert item.bid == 1210
    assert item.ask == 1215
