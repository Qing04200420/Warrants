from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncio
import os

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import clear, history, init_db, record_iv_sample, save
from .estimation import estimate_warrant
from .models import (
    Analysis,
    AnalyzeRequest,
    EstimateRequest,
    StockScoreRequest,
    StockScoreResponse,
    WarrantEstimate,
    WarrantRecommendationRequest,
    WarrantRecommendationResponse,
)
from .providers import fetch_stock_quote, fetch_warrant
from .recommendations import recommend_warrants
from .scoring import calculate_score
from .stock_history import StockHistoryProviderError, fetch_stock_history
from .stock_scoring import calculate_stock_score
from .twse_warrants import fetch_twse_warrant_market_data
from .twse_openapi import fetch_official_warrants
from .yuanta import YuantaNotConfigured, fetch_yuanta_quote


@asynccontextmanager
async def lifespan(_: FastAPI):
    # FastAPI 啟動時先建立分析紀錄與歷史 IV 資料表。
    init_db()
    yield


app = FastAPI(title="台股權證評分 API", version="1.0.0", lifespan=lifespan)
# 除了本機開發網址，也允許正式 GitHub Pages 前端呼叫 API。
default_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://192.168.1.67:3000",
    "https://qing04200420.github.io",
]
configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(default_origins + configured_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "broker_market_data": "shioaji" if os.getenv("SHIOAJI_API_URL") else "public_fallback",
        "yuanta_market_data": "configured" if os.getenv("YUANTA_GATEWAY_URL") else "fallback",
    }


@app.post("/api/warrants/estimate", response_model=WarrantEstimate)
async def estimate(request: EstimateRequest):
    """依權證代號自動載入最新條款與行情，並回傳理論價格。"""
    try:
        return await estimate_warrant(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except http_error_types() as exc:
        raise HTTPException(status_code=502, detail="官方或券商行情服務暫時無法連線") from exc


@app.post("/api/stocks/score", response_model=StockScoreResponse)
async def score_stock(request: StockScoreRequest):
    """依大盤、日週線、價量、動能及交易計畫計算股票多頭分數。"""
    try:
        history_data = await fetch_stock_history(request.code)
        return calculate_stock_score(history_data, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StockHistoryProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except http_error_types() as exc:
        raise HTTPException(status_code=502, detail="股票歷史行情服務暫時無法連線") from exc


@app.post("/api/warrants/recommend", response_model=WarrantRecommendationResponse)
async def recommend(request: WarrantRecommendationRequest):
    """依標的現價、履約價與剩餘期間推薦認購權證候選名單。"""
    try:
        warrants = await fetch_official_warrants()
        items = recommend_warrants(
            list(warrants.values()),
            underlying_name=request.underlying_name,
            stock_price=request.stock_price,
            limit=request.limit,
        )
        return WarrantRecommendationResponse(
            underlying_code=request.underlying_code,
            underlying_name=request.underlying_name,
            stock_price=request.stock_price,
            recommendations=items,
        )
    except http_error_types() as exc:
        raise HTTPException(status_code=502, detail="證交所權證基本資料暫時無法連線") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="證交所權證基本資料格式暫時無法解析") from exc


@app.post("/api/warrants/analyze", response_model=Analysis)
async def analyze(request: AnalyzeRequest):
    """整合基本資料、標的行情及 TWSE 盤後資料後，計分並保存結果。"""
    try:
        # 先取得權證基本條件，再用標的代號查詢股票行情。
        name, stock_stub, metrics = await fetch_warrant(request.code)
        async def load_quote():
            try:
                return await fetch_yuanta_quote(stock_stub.code, stock_stub.name), None
            except (YuantaNotConfigured, httpx.HTTPError, ValueError, TypeError):
                return await asyncio.to_thread(fetch_stock_quote, stock_stub)

        quote_future = asyncio.create_task(load_quote())
        market_future = asyncio.create_task(fetch_twse_warrant_market_data(stock_stub.code, request.code, name))
        stock, warning = await quote_future
        try:
            # TWSE 是補充資料來源；連線失敗不應讓整個分析 API 失敗。
            market = await market_future
            if market is None:
                twse_warning = "TWSE 盤後資料找不到此權證，可能已下市或當日沒有造市報價。"
            else:
                iv_std = None
                iv_count = 0
                iv_std_source = None
                if market.implied_vol is not None:
                    # 同一權證每天只保留一筆 IV，用最近 14 筆計算穩定度。
                    iv_std, iv_count = record_iv_sample(
                        request.code,
                        market.observed_on,
                        market.implied_vol,
                    )
                if iv_std is not None:
                    iv_std_source = "twse_rolling_14d"
                elif market.period_max_iv_change is not None:
                    # TWSE 公開的是 14 日委買 IV 最大變動，不是標準差；
                    # 歷史筆數不足時僅作為有明確標示的暫代穩定度指標。
                    iv_std = market.period_max_iv_change
                    iv_std_source = "twse_14d_max_change_proxy"
                metrics = metrics.model_copy(
                    # Pydantic model_copy 可保留基本資料，只覆寫盤後欄位。
                    update={
                        "implied_vol": market.implied_vol,
                        "iv_std": iv_std,
                        "bid_ask_spread": market.bid_ask_spread,
                        "bid_volume": market.bid_volume,
                        "ask_volume": market.ask_volume,
                        "market_data_source": "TWSE 權證資訊揭露平台（盤後）",
                        "market_data_date": market.observed_on,
                        "iv_std_source": iv_std_source,
                        "iv_history_count": iv_count,
                    }
                )
                twse_warning = None
        except Exception:
            if not market_future.done():
                market_future.cancel()
            twse_warning = "TWSE 盤後權證資料暫時無法連線，評分保留可取得的資料。"
        warning = " ".join(item for item in (warning, twse_warning) if item) or None
        # 所有可取得欄位合併完成後才計分，避免使用尚未補值的資料。
        score, rating, items = calculate_score(metrics)
        result = Analysis(warrant_code=request.code, warrant_name=name, stock=stock, metrics=metrics, score=score, rating=rating, score_items=items, analyzed_at=datetime.now(timezone.utc), warning=warning)
        payload = result.model_dump(mode="json")
        result.id = save(payload)
        return result
    except http_error_types() as exc:
        raise HTTPException(status_code=502, detail="上游行情網站暫時無法連線") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def http_error_types():
    # 延遲載入 httpx，讓此函式只負責集中定義上游網路錯誤類型。
    import httpx
    return (httpx.HTTPError,)


@app.get("/api/history", response_model=list[Analysis])
def get_history(code: str | None = Query(default=None, pattern=r"^[0-9]{6}$"), limit: int = Query(default=30, ge=1, le=200)):
    return history(code, limit)


@app.delete("/api/history", status_code=204)
def delete_history():
    clear()
