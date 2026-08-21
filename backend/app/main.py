from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import clear, history, init_db, save
from .models import Analysis, AnalyzeRequest
from .providers import fetch_stock_quote, fetch_warrant
from .scoring import calculate_score


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
