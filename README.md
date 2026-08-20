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

## 資料來源與限制

- 權證條件：元富「新鉅亨」公開個股基本資料頁。
- 標的即時行情：`twstock` 優先；盤後或失敗時改用 `yfinance`（上市 `.TW`、上櫃 `.TWO`）最近日線。
- 公開網站格式可能異動；正式營運建議改接有 SLA／授權的行情 API，並依來源條款設定快取與頻率限制。
- 分數是產品篩選指標，不是投資建議。公式位於 `backend/app/scoring.py`，權重可集中調整。

## API

- `POST /api/warrants/analyze`：查詢並保存快照，body: `{ "code": "067185" }`
- `GET /api/history?code=067185&limit=30`：歷史紀錄
- `DELETE /api/history`：清除歷史紀錄
- `GET /api/health`：健康檢查

## 測試

```powershell
cd backend
python -m pytest
```

