# 台股權證評分系統

輸入六碼權證代號，系統會解析對應標的、顯示標的行情，並依到期天數、履約價、權證價、執行比例、Delta、Theta、價內外程度及有效槓桿計算 0–100 分。每次查詢會寫入 SQLite，供歷史比較。

## 啟動

需求：Python 3.11+、Node.js 20+

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

另開終端：

```powershell
cd frontend
npm install
npm run dev
```

開啟 `http://localhost:5173`。Swagger 文件在 `http://localhost:8000/docs`。

前端共有「權證評分」、「標的評分」及「價格試算」三個頁面。標的評分頁會要求輸入進場價、停損價與目標價，再分析大盤、日週線、價格結構、量價及動能。

## 資料來源與限制

- 權證估價條款：臺灣證券交易所 OpenAPI 的最新履約價、行使比例與最後交易日。
- 波動率：TWSE 權證資訊揭露平台委買隱含波動率；官方無資料時才使用清楚標示的 30% 預設值。
- 正式券商行情：可選接永豐金證券 Shioaji HTTP API；未設定時以 `twstock` 與 `yfinance` 作公開行情備援。
- 股票技術分析：Shioaji 啟用時分段取得 Kbars 並彙整日線；未啟用時優先採交易所官方日線，Yahoo Finance 作備援。個股與加權指數分開快取；盤中快取 10 分鐘，收盤後快取到下一個交易日開盤，且併發查詢會共用同一次下載。
- 舊評分頁的權證補充欄位仍使用元富「新鉅亨」公開資料頁。
- 分數是產品篩選指標，不是投資建議。公式位於 `backend/app/scoring.py`，權重可集中調整。

## API

- `POST /api/warrants/analyze`：以六位數字權證代號查詢並保存快照，body: `{ "code": "067185" }`
- `POST /api/warrants/estimate`：自動載入最新條款、行情及隱波並估價；權證代號僅接受六位數字，body 最少只需 `{ "code": "067185" }`，亦可傳入 `stock_price`、`implied_vol`、`valuation_date`、`risk_free_rate` 覆寫情境。
- `POST /api/stocks/score`：股票多頭技術面評分，body: `{ "code": "2330", "entry_price": 2400, "stop_loss_price": 2300, "target_price": 2600 }`。
- `POST /api/warrants/recommend`：依標的現價、履約價與剩餘期間推薦認購權證候選，body: `{ "underlying_code": "2330", "underlying_name": "台積電", "stock_price": 2400, "limit": 5 }`。
- `GET /api/history?code=067185&limit=30`：歷史紀錄
- `DELETE /api/history`：清除歷史紀錄
- `GET /api/health`：健康檢查

股票分數滿分 100：大盤環境 10、日線趨勢 25、週線趨勢 10、價格結構 10、量價 10、RSI／MACD／KD 動能 15、風險報酬 20。規則集中於 `backend/app/stock_scoring.py`，回應會附上每項實際數值、成立狀態與得分。

## 測試

```powershell
cd backend
python -m pytest
```

## 正式券商行情（Shioaji）

先依[永豐金證券 Shioaji 官方說明](https://sinotrade.github.io/tutor/simulation/)啟動已登入的 HTTP server，再設定後端環境變數：

```powershell
$env:SHIOAJI_API_URL = "http://127.0.0.1:8080"
uvicorn app.main:app --reload --port 8000
```

本專案只呼叫 Shioaji 的契約與市場資料端點，不會呼叫下單、改單或帳務端點。券商服務未設定或離線時，系統會標示並降級至公開行情備援。請勿將 `SJ_API_KEY` 或 `SJ_SEC_KEY` 提交到版本庫。

## 元大證券 SPARK 即時行情

SPARK 使用需申請的官方原生元件。建議在已安裝 SDK 的主機常駐唯讀行情 Gateway，並設定 `YUANTA_GATEWAY_URL`、`YUANTA_GATEWAY_TOKEN` 與選用的 `YUANTA_GATEWAY_TIMEOUT`。Gateway 提供 `GET /v1/quotes/{股票代號}`，回傳 `name`、`price`、`open`、`high`、`low`、`volume`、`quoted_at`。未設定或逾時時會自動降級至既有公開行情來源。

