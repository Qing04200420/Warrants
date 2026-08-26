from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


class StockScoreRequest(BaseModel):
    """股票多頭技術面評分與交易計畫。"""
    code: str = Field(pattern=r"^[0-9A-Z]{4,6}$", examples=["2330"])
    entry_price: float = Field(gt=0)
    stop_loss_price: float = Field(gt=0)
    target_price: float = Field(gt=0)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_stock_code(cls, value):
        return str(value).strip().upper()

    @model_validator(mode="after")
    def validate_long_plan(self):
        if not self.stop_loss_price < self.entry_price < self.target_price:
            raise ValueError("多頭交易計畫必須符合：停損價 < 進場價 < 目標價")
        return self


class StockScoreItem(BaseModel):
    group: str
    key: str
    label: str
    score: float
    max_score: float
    passed: bool
    note: str


class StockScoreResponse(BaseModel):
    code: str
    name: str
    as_of: str
    close: float
    score: float
    rating: str
    summary: str
    market: dict[str, float | bool | str | None]
    daily: dict[str, float | bool | str | None]
    weekly: dict[str, float | bool | str | None]
    price_structure: dict[str, float | bool | str | None]
    volume: dict[str, float | bool | str | None]
    momentum: dict[str, float | bool | str | None]
    risk_reward: dict[str, float | bool | str | None]
    items: list[StockScoreItem]
    source: str
    warning: str | None = None


class WarrantRecommendationRequest(BaseModel):
    underlying_code: str = Field(pattern=r"^[0-9A-Z]{4,6}$", examples=["2330"])
    underlying_name: str = Field(min_length=1, max_length=40, examples=["台積電"])
    stock_price: float = Field(gt=0)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("underlying_code", mode="before")
    @classmethod
    def normalize_underlying_code(cls, value):
        return str(value).strip().upper()


class WarrantRecommendation(BaseModel):
    code: str
    name: str
    strike_price: float
    exercise_ratio: float
    last_trading_date: str
    expiry_date: str
    days_to_last_trading: int
    moneyness: str
    strike_gap_percent: float
    match_score: float
    reason: str


class WarrantRecommendationResponse(BaseModel):
    underlying_code: str
    underlying_name: str
    stock_price: float
    recommendations: list[WarrantRecommendation]
    source: str = "TWSE 上市權證基本條款"
    notice: str = "推薦為基本條款初選，不含即時流動性與隱含波動率；交易前請再查看權證評分。"


class AnalyzeRequest(BaseModel):
    """分析端點輸入：接受數字或含英文字尾的六碼權證代號。"""
    code: str = Field(pattern=r"^[0-9A-Z]{6}$", examples=["067185", "03002T"])

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return str(value).strip().upper()


class EstimateRequest(AnalyzeRequest):
    """代號為必填；其他欄位空白時自動採最新市場資料。"""
    stock_price: float | None = Field(default=None, ge=0)
    implied_vol: float | None = Field(default=None, gt=0, le=5)
    valuation_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    risk_free_rate: float = Field(default=0.015, ge=-0.1, le=1)


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


class WarrantContract(BaseModel):
    code: str
    name: str
    call_put: str
    type_label: str
    underlying_code: str
    underlying_name: str
    strike_price: float
    exercise_ratio: float
    last_trading_date: str
    expiry_date: str
    terms_source: str
    terms_date: str


class WarrantQuote(BaseModel):
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    source: str
    quoted_at: str | None = None


class WarrantEstimate(BaseModel):
    contract: WarrantContract
    stock: StockQuote
    warrant_quote: WarrantQuote
    valuation_date: str
    trading_days_to_expiry: int
    market_holidays: list[str]
    implied_vol: float
    volatility_source: str
    risk_free_rate: float
    theoretical_price: float
    intrinsic_value: float
    time_value: float
    delta: float
    data_sources: list[str]
    warning: str | None = None


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
