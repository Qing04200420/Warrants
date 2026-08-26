"""把官方條款、券商行情、TWSE 隱波與估價模型組成單一流程。"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from .broker import ShioajiHttpClient
from .models import EstimateRequest, StockQuote, WarrantContract, WarrantEstimate, WarrantQuote
from .pricing import price_warrant, trading_days_between
from .providers import fetch_stock_quote, fetch_warrant
from .twse_openapi import fetch_market_holidays, fetch_official_warrant
from .twse_warrants import fetch_twse_warrant_market_data


async def estimate_warrant(request: EstimateRequest) -> WarrantEstimate:
    official = await fetch_official_warrant(request.code)
    broker = ShioajiHttpClient()
    warnings: list[str] = []
    sources = ["臺灣證券交易所 OpenAPI（最新權證條款）"]

    broker_warrant = None
    if broker.enabled:
        try:
            broker_warrant = await broker.find_warrant(request.code, official.underlying_name)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            warnings.append("Shioaji 券商服務目前無法連線，行情已切換至公開資料備援。")

    stock_stub: StockQuote | None = None
    legacy_metrics = None
    if broker_warrant is not None:
        underlying_code = broker_warrant.underlying_code
        underlying_name = broker_warrant.underlying_name
        name = broker_warrant.name or official.name
        call_put = broker_warrant.call_put
        strike_price = broker_warrant.strike_price
        exercise_ratio = broker_warrant.exercise_ratio
        last_trading_date = date.fromisoformat(broker_warrant.last_trading_date)
        expiry_date = date.fromisoformat(broker_warrant.expiry_date)
        terms_source = "永豐金證券 Shioaji / 臺灣證券交易所"
        sources.append("永豐金證券 Shioaji 契約與行情 API")
    else:
        # TWSE 權證基本檔只有標的名稱；無券商服務時用既有資料頁補標的代號，
        # 履約價與行使比例仍一律採官方 OpenAPI 的最新值。
        name, stock_stub, legacy_metrics = await fetch_warrant(request.code)
        underlying_code = stock_stub.code
        underlying_name = stock_stub.name or official.underlying_name
        name = official.name or name
        call_put = official.call_put
        strike_price = official.strike_price
        exercise_ratio = official.exercise_ratio
        last_trading_date = official.last_trading_date
        expiry_date = official.expiry_date
        terms_source = "臺灣證券交易所 OpenAPI"

    contract = WarrantContract(
        code=request.code,
        name=name,
        call_put=call_put,
        type_label="認購" if call_put == "C" else "認售",
        underlying_code=underlying_code,
        underlying_name=underlying_name,
        strike_price=strike_price,
        exercise_ratio=exercise_ratio,
        last_trading_date=last_trading_date.isoformat(),
        expiry_date=expiry_date.isoformat(),
        terms_source=terms_source,
        terms_date=official.data_date.isoformat(),
    )

    stock = None
    warrant_quote = WarrantQuote(source="無可用行情")
    if broker.enabled and broker_warrant is not None:
        try:
            info = await broker.contract_info(underlying_code)
            stock_snapshot = await broker.snapshot(
                code=underlying_code,
                security_type=str(info.get("security_type", "STK")),
                exchange=str(info.get("exchange", "TSE")),
            )
            if stock_snapshot is not None:
                stock = StockQuote(
                    code=underlying_code,
                    name=str(info.get("name") or underlying_name),
                    price=stock_snapshot.close,
                    open=stock_snapshot.open,
                    high=stock_snapshot.high,
                    low=stock_snapshot.low,
                    volume=stock_snapshot.total_volume,
                    source="永豐金證券 Shioaji",
                    quoted_at=stock_snapshot.quoted_at,
                )
            # Shioaji 的權證契約類型為 WRT；部分舊版 server 不支援快照時安靜降級。
            try:
                quote = await broker.snapshot(code=request.code, security_type="WRT", exchange="TSE")
                if quote is not None:
                    warrant_quote = WarrantQuote(
                        price=quote.close,
                        bid=quote.bid,
                        ask=quote.ask,
                        source="永豐金證券 Shioaji",
                        quoted_at=quote.quoted_at,
                    )
            except httpx.HTTPError:
                pass
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            warnings.append("券商即時快照取得失敗，標的價格已改用公開行情備援。")

    if stock is None:
        if stock_stub is None:
            try:
                _, stock_stub, legacy_metrics = await fetch_warrant(request.code)
            except Exception:
                stock_stub = StockQuote(
                    code=underlying_code,
                    name=underlying_name,
                    source="待取得",
                )
        stock, stock_warning = fetch_stock_quote(stock_stub)
        if stock_warning:
            warnings.append(stock_warning)
        sources.append(stock.source)
        if legacy_metrics is not None:
            warrant_quote = WarrantQuote(
                price=legacy_metrics.warrant_price,
                source="公開權證行情頁（盤後備援）",
            )

    implied_vol = None
    volatility_source = "使用者輸入"
    if request.implied_vol is None:
        try:
            market = await fetch_twse_warrant_market_data(underlying_code, request.code, name)
            if market is not None and market.implied_vol is not None:
                implied_vol = market.implied_vol
                volatility_source = "TWSE 權證資訊揭露平台委買隱波"
                sources.append("TWSE 權證資訊揭露平台（盤後）")
        except Exception:
            warnings.append("TWSE 委買隱波暫時無法取得。")
    else:
        implied_vol = request.implied_vol

    if implied_vol is None:
        implied_vol = 0.30
        volatility_source = "系統預設 30%（TWSE 隱波無資料）"
        warnings.append("目前查無委買隱波，估價暫採年化波動率 30%，請依券商報價調整。")

    valuation_date = (
        date.fromisoformat(request.valuation_date)
        if request.valuation_date
        else datetime.now(ZoneInfo("Asia/Taipei")).date()
    )
    try:
        holidays = await fetch_market_holidays()
        sources.append("臺灣證券交易所開休市日 OpenAPI")
    except (httpx.HTTPError, ValueError):
        holidays = set()
        warnings.append("TWSE 休市日資料暫時無法取得，剩餘期間僅排除週末。")
    relevant_holidays = {
        item for item in holidays if valuation_date < item <= last_trading_date
    }
    trading_days = trading_days_between(valuation_date, last_trading_date, holidays)
    stock_price = request.stock_price if request.stock_price is not None else stock.price
    if stock_price is None:
        raise ValueError("查無標的價格，請手動輸入標的股價後再試算")
    priced = price_warrant(
        call_put=call_put,
        stock_price=stock_price,
        strike_price=strike_price,
        exercise_ratio=exercise_ratio,
        trading_days=trading_days,
        volatility=implied_vol,
        risk_free_rate=request.risk_free_rate,
    )

    # 使用者覆寫股價時，回應中的行情仍保留來源，但估值顯示實際採用數值。
    if request.stock_price is not None:
        stock = stock.model_copy(update={"price": request.stock_price})

    return WarrantEstimate(
        contract=contract,
        stock=stock,
        warrant_quote=warrant_quote,
        valuation_date=valuation_date.isoformat(),
        trading_days_to_expiry=trading_days,
        market_holidays=sorted(item.isoformat() for item in relevant_holidays),
        implied_vol=implied_vol,
        volatility_source=volatility_source,
        risk_free_rate=request.risk_free_rate,
        theoretical_price=priced.theoretical_price,
        intrinsic_value=priced.intrinsic_value,
        time_value=priced.time_value,
        delta=priced.delta,
        data_sources=list(dict.fromkeys(source for source in sources if source)),
        warning=" ".join(dict.fromkeys(warnings)) or None,
    )
