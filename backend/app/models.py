from datetime import datetime
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$", examples=["067185"])


class StockQuote(BaseModel):
    code: str
    name: str
    price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    source: str
    quoted_at: str | None = None


class WarrantMetrics(BaseModel):
    days_to_expiry: int
    strike_price: float
    warrant_price: float
    exercise_ratio: float
    delta: float
    theta: float
    moneyness_percent: float
    moneyness_label: str
    effective_leverage: float
    expiry_date: str
    # Optional market-derived fields for enhanced scoring
    implied_vol: float | None = None
    iv_std: float | None = None
    bid_ask_spread: float | None = None
    bid_volume: int | None = None
    ask_volume: int | None = None


class ScoreItem(BaseModel):
    key: str
    label: str
    score: float
    max_score: float
    note: str


class Analysis(BaseModel):
    id: int | None = None
    warrant_code: str
    warrant_name: str
    stock: StockQuote
    metrics: WarrantMetrics
    score: float
    rating: str
    score_items: list[ScoreItem]
    analyzed_at: datetime
    warning: str | None = None

