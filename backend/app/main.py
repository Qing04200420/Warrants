from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import clear, history, init_db, record_iv_sample, save
from .models import Analysis, AnalyzeRequest
from .providers import fetch_stock_quote, fetch_warrant
from .scoring import calculate_score
from .twse_warrants import fetch_twse_warrant_market_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="台股權證評分 API", version="1.0.0", lifespan=lifespan)
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
    return {"status": "ok"}


@app.post("/api/warrants/analyze", response_model=Analysis)
async def analyze(request: AnalyzeRequest):
    try:
        name, stock_stub, metrics = await fetch_warrant(request.code)
        stock, warning = fetch_stock_quote(stock_stub)
        try:
            market = await fetch_twse_warrant_market_data(stock_stub.code, request.code, name)
            if market is None:
                twse_warning = "TWSE 盤後資料找不到此權證，可能已下市或當日沒有造市報價。"
            else:
                iv_std = None
                iv_count = 0
                iv_std_source = None
                if market.implied_vol is not None:
                    iv_std, iv_count = record_iv_sample(
                        request.code,
                        market.observed_on,
                        market.implied_vol,
                    )
                if iv_std is not None:
                    iv_std_source = "twse_rolling_14d"
                elif market.period_max_iv_change is not None:
                    # TWSE publishes the 14-day maximum Buy-1 IV change, not
                    # a standard deviation. Use it only as an explicitly
                    # labelled stability proxy until two daily samples exist.
                    iv_std = market.period_max_iv_change
                    iv_std_source = "twse_14d_max_change_proxy"
                metrics = metrics.model_copy(
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
            twse_warning = "TWSE 盤後權證資料暫時無法連線，評分保留可取得的資料。"
        warning = " ".join(item for item in (warning, twse_warning) if item) or None
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
    import httpx
    return (httpx.HTTPError,)


@app.get("/api/history", response_model=list[Analysis])
def get_history(code: str | None = Query(default=None, pattern=r"^\d{6}$"), limit: int = Query(default=30, ge=1, le=200)):
    return history(code, limit)


@app.delete("/api/history", status_code=204)
def delete_history():
    clear()
