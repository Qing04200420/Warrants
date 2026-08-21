from datetime import datetime
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """分析端點輸入：目前接受傳統六碼數字權證代號。"""
    code: str = Field(pattern=r"^\d{6}$", examples=["067185"])


class StockQuote(BaseModel):
    """標的股票行情；來源無資料時價格欄位允許為空。"""
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
    """權證評分使用的基本參數與盤後造市資料。"""
    # 基本條件由權證資料頁取得。
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
    # 以下為 TWSE 盤後衍生欄位；官方顯示「-」時保留 None，不誤填為 0。
    implied_vol: float | None = None
    iv_std: float | None = None
    bid_ask_spread: float | None = None
    bid_volume: int | None = None
    ask_volume: int | None = None
    market_data_source: str | None = None
    market_data_date: str | None = None
    iv_std_source: str | None = None
    iv_history_count: int | None = None


class ScoreItem(BaseModel):
    """單一評分項目的得分、滿分與可讀說明。"""
    key: str
    label: str
    score: float
    max_score: float
    note: str


class Analysis(BaseModel):
    """前端顯示及歷史紀錄使用的完整分析回應。"""
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
