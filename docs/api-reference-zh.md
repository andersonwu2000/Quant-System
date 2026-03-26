# 量化交易系統 — API 手冊

## 概覽

- **基礎 URL：** `http://localhost:8000`
- **API 前綴：** `/api/v1`
- **互動式文件：** `/docs`（Swagger UI）、`/redoc`（ReDoc）
- **內容格式：** `application/json`

## 認證

### API Key

在每個請求中加入 `X-API-Key` 標頭：

```
X-API-Key: your-api-key
```

### JWT Token

也可使用 JWT Bearer Token 認證：

```
Authorization: Bearer <jwt-token>
```

JWT Token 透過登入端點取得（見下方 `POST /api/v1/auth/login`），包含角色宣告。Token 預設 24 小時後過期（可透過 `QUANT_JWT_EXPIRE_MINUTES` 設定）。

### 角色階層

| 角色 | 等級 | 權限 |
|------|------|------|
| `viewer` | 0 | 唯讀存取 |
| `researcher` | 1 | + 回測 |
| `trader` | 2 | + 訂單管理、策略控制 |
| `risk_manager` | 3 | + 風控規則管理、緊急熔斷 |
| `admin` | 4 | 完整存取 |

高等級角色繼承低等級角色的所有權限。

---

### 速率限制

API 設有速率限制，超過限制時回傳 `429 Too Many Requests`：

| 端點 | 限制 |
|------|------|
| 一般端點 | 60 次/分鐘 |
| `POST /api/v1/backtest` | 10 次/分鐘 |

---

## REST 端點

### 認證

#### `POST /api/v1/auth/login`

使用 API Key 登入，取得 JWT Token。**不需要預先認證。**

**請求主體：**
```json
{
  "api_key": "your-api-key"
}
```

**回應** `200`：
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

同時在 `Set-Cookie` 標頭中設定 httpOnly cookie `access_token`。

**回應** `401`：
```json
{"detail": "Invalid API key"}
```

#### `POST /api/v1/auth/change-password`

變更密碼。需要認證。

**請求主體：**
```json
{
  "current_password": "old-password",
  "new_password": "new-password"
}
```

**回應** `200`：
```json
{"detail": "Password changed"}
```

#### `POST /api/v1/auth/logout`

登出，清除認證 cookie。

**回應** `200`：
```json
{"detail": "Logged out"}
```

---

### 系統

#### `GET /api/v1/system/health`

健康檢查。**不需要認證。**

**回應** `200`：
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

#### `GET /api/v1/system/status`

系統狀態總覽。

**回應** `200`：
```json
{
  "mode": "backtest",
  "uptime_seconds": 3600.5,
  "strategies_running": 2,
  "data_source": "yahoo",
  "database": "postgresql"
}
```

#### `GET /api/v1/system/metrics`

基礎系統指標（請求計數等）。

**回應** `200`：
```json
{
  "total_requests": 1234,
  "active_websockets": 3,
  "uptime_seconds": 7200.0
}
```

---

### 投資組合

#### `GET /api/v1/portfolio`

取得完整投資組合快照。

**回應** `200`：
```json
{
  "nav": 10500000.0,
  "cash": 5250000.0,
  "gross_exposure": 5250000.0,
  "net_exposure": 4200000.0,
  "positions_count": 5,
  "daily_pnl": 15000.0,
  "daily_pnl_pct": 0.0014,
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 1000.0,
      "avg_cost": 150.0,
      "market_price": 155.0,
      "market_value": 155000.0,
      "unrealized_pnl": 5000.0,
      "weight": 0.0148
    }
  ],
  "as_of": "2024-01-15T16:00:00"
}
```

#### `GET /api/v1/portfolio/positions`

取得所有持倉列表。

**回應** `200`：
```json
[
  {
    "symbol": "AAPL",
    "quantity": 1000.0,
    "avg_cost": 150.0,
    "market_price": 155.0,
    "market_value": 155000.0,
    "unrealized_pnl": 5000.0,
    "weight": 0.0148
  }
]
```

#### `GET /api/v1/portfolio/saved`

列出所有已儲存的投資組合。

**回應** `200`：
```json
{
  "portfolios": [
    {"id": "pf-001", "name": "主策略", "created_at": "2024-01-01T00:00:00"}
  ]
}
```

#### `POST /api/v1/portfolio/saved`

建立新的持久化投資組合。

**請求主體：**
```json
{
  "name": "我的組合",
  "holdings": {"AAPL": 0.3, "MSFT": 0.7}
}
```

**回應** `201`：
```json
{"id": "pf-002", "name": "我的組合", "holdings": {"AAPL": 0.3, "MSFT": 0.7}}
```

#### `GET /api/v1/portfolio/saved/{portfolio_id}`

取得指定投資組合的詳細資訊。

#### `DELETE /api/v1/portfolio/saved/{portfolio_id}`

刪除指定投資組合。

#### `POST /api/v1/portfolio/saved/{portfolio_id}/rebalance-preview`

根據策略計算再平衡建議交易。

**請求主體：**
```json
{
  "strategy": "momentum",
  "params": {}
}
```

**回應** `200`：包含建議交易列表（透過 `weights_to_orders()` 計算）。

#### `GET /api/v1/portfolio/saved/{portfolio_id}/trades`

取得指定投資組合的歷史交易紀錄。

#### `POST /api/v1/portfolio/optimize`

投資組合最佳化（支援 14 種方法：EW、InverseVol、RiskParity、MVO、BlackLitterman、HRP 等）。

#### `POST /api/v1/portfolio/risk-analysis`

投資組合風險分析（共變異數估計、風險貢獻等）。

#### `POST /api/v1/portfolio/hedge-recommendations`

取得貨幣避險建議。

---

### 策略

#### `GET /api/v1/strategies`

列出所有已註冊的策略。

**回應** `200`：
```json
{
  "strategies": [
    {"name": "momentum_12_1", "status": "running", "pnl": 25000.0},
    {"name": "mean_reversion", "status": "stopped", "pnl": 0.0}
  ]
}
```

#### `GET /api/v1/strategies/{strategy_id}`

取得特定策略的詳細資訊。

**路徑參數：**
- `strategy_id`（字串）：策略名稱

**回應** `200`：
```json
{"name": "momentum_12_1", "status": "running", "pnl": 25000.0}
```

**回應** `404`：
```json
{"detail": "Strategy not found: unknown_strategy", "code": "error"}
```

#### `POST /api/v1/strategies/{strategy_id}/start`

啟動策略。

**請求主體**（選用）：
```json
{"params": {"lookback": 252}}
```

**回應** `200`：
```json
{"name": "momentum_12_1", "status": "running", "pnl": 0.0}
```

#### `POST /api/v1/strategies/{strategy_id}/stop`

停止運行中的策略。

**回應** `200`：
```json
{"name": "momentum_12_1", "status": "stopped", "pnl": 25000.0}
```

---

### 訂單

#### `GET /api/v1/orders`

列出訂單，可按狀態篩選。支援分頁。

**查詢參數：**
- `status`（字串，選用）：按狀態篩選 — `"open"` 或 `"filled"`
- `limit`（整數，選用，預設 50，最大 200）：每頁筆數
- `offset`（整數，選用，預設 0）：跳過筆數

**回應** `200`：
```json
[
  {
    "id": "ord-abc123",
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 100.0,
    "price": 150.0,
    "status": "FILLED",
    "filled_qty": 100.0,
    "filled_avg_price": 150.05,
    "commission": 21.38,
    "created_at": "2024-01-15T10:30:00",
    "strategy_id": "momentum_12_1"
  }
]
```

#### `POST /api/v1/orders`

建立新訂單。需要 `trader` 以上角色。

**請求主體：**
```json
{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "price": 150.0
}
```

**回應** `200`：
```json
{
  "id": "ord-abc123",
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100.0,
  "price": 150.0,
  "status": "PENDING"
}
```

#### `PUT /api/v1/orders/{order_id}`

修改訂單（價格或數量）。僅限 `PENDING` 狀態的訂單。

**請求主體：**
```json
{
  "price": 151.0,
  "quantity": 200
}
```

#### `DELETE /api/v1/orders/{order_id}`

取消訂單。僅限 `PENDING` 狀態的訂單。

**回應** `200`：回傳取消後的訂單物件。

---

### 回測

#### `POST /api/v1/backtest`

提交非同步回測任務。

**請求主體：**
```json
{
  "strategy": "momentum",
  "universe": ["AAPL", "MSFT", "GOOGL"],
  "start": "2023-01-01",
  "end": "2024-12-31",
  "initial_cash": 10000000.0,
  "params": {},
  "slippage_bps": 5.0,
  "commission_rate": 0.001425,
  "rebalance_freq": "weekly"
}
```

| 欄位 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `strategy` | string | 必填 | 策略名稱 |
| `universe` | string[] | 必填 | 股票代碼列表 |
| `start` | string | `"2020-01-01"` | 開始日期（YYYY-MM-DD） |
| `end` | string | `"2025-12-31"` | 結束日期（YYYY-MM-DD） |
| `initial_cash` | float | `10000000.0` | 初始資金 |
| `params` | object | `{}` | 策略專屬參數 |
| `slippage_bps` | float | `5.0` | 滑價（基點） |
| `commission_rate` | float | `0.001425` | 手續費率 |
| `rebalance_freq` | string | `"weekly"` | `"daily"`、`"weekly"`、`"monthly"` |

**回應** `202`：
```json
{
  "task_id": "bt-abc123",
  "status": "running",
  "strategy_name": "momentum"
}
```

#### `GET /api/v1/backtest/{task_id}`

查詢回測狀態與摘要。

**回應** `200`（進行中）：
```json
{
  "task_id": "bt-abc123",
  "status": "running",
  "strategy_name": "momentum",
  "progress_current": 150,
  "progress_total": 500
}
```

**回應** `200`（已完成）：
```json
{
  "task_id": "bt-abc123",
  "status": "completed",
  "strategy_name": "momentum_12_1",
  "total_return": 0.1694,
  "annual_return": 0.0819,
  "sharpe": 1.06,
  "max_drawdown": 0.0804,
  "total_trades": 54
}
```

**回應** `200`（失敗）：
```json
{
  "task_id": "bt-abc123",
  "status": "failed",
  "strategy_name": "momentum",
  "error": "No data loaded for any symbol in universe"
}
```

**回應** `429`（並行任務過多）：
```json
{"detail": "Too many concurrent backtests (max 50)"}
```

#### `GET /api/v1/backtest/{task_id}/result`

取得完整回測結果及所有績效指標。

**回應** `200`：
```json
{
  "strategy_name": "momentum_12_1",
  "start_date": "2023-01-03",
  "end_date": "2024-12-30",
  "initial_cash": 10000000.0,
  "total_return": 0.1694,
  "annual_return": 0.0819,
  "sharpe": 1.06,
  "sortino": 0.99,
  "calmar": 1.02,
  "max_drawdown": 0.0804,
  "max_drawdown_duration": 87,
  "volatility": 0.0773,
  "total_trades": 54,
  "win_rate": 0.647,
  "total_commission": 25962.0,
  "nav_series": [
    {"date": "2023-01-03", "nav": 10000000.0},
    {"date": "2023-01-04", "nav": 10015000.0}
  ]
}
```

#### `POST /api/v1/backtest/walk-forward`

Walk-forward 前進式分析。將資料切割為訓練/測試視窗，逐段回測驗證策略穩健性。

**請求主體：**
```json
{
  "strategy": "momentum",
  "universe": ["AAPL", "MSFT"],
  "start": "2020-01-01",
  "end": "2024-12-31",
  "train_months": 12,
  "test_months": 3
}
```

#### `POST /api/v1/backtest/randomized`

隨機化回測（Bootstrap）。

#### `POST /api/v1/backtest/pbo`

機率回測過度擬合（PBO）檢定。

#### `POST /api/v1/backtest/stress-test`

壓力測試回測。

#### `POST /api/v1/backtest/grid-search`

參數網格搜尋回測。

#### `POST /api/v1/backtest/{task_id}/validate`

對已完成的回測執行驗證閘門（11 項檢查）。

#### `POST /api/v1/backtest/kfold`

K-fold 交叉驗證回測。

#### `POST /api/v1/backtest/full-validation`

完整驗證流程（整合所有驗證方法）。

#### `GET /api/v1/backtest/history`

取得回測歷史紀錄列表。

---

### 風控

#### `GET /api/v1/risk/rules`

列出所有風控規則及其啟用狀態。

**回應** `200`：
```json
[
  {"name": "max_position_weight_0.1", "enabled": true},
  {"name": "max_order_notional_0.1", "enabled": true},
  {"name": "daily_drawdown_0.03", "enabled": true},
  {"name": "fat_finger_0.05", "enabled": true},
  {"name": "max_daily_trades_100", "enabled": true},
  {"name": "max_order_vs_adv_0.1", "enabled": true}
]
```

#### `PUT /api/v1/risk/rules/{rule_name}`

啟用或停用風控規則。

**請求主體：**
```json
{"enabled": false}
```

**回應** `200`：
```json
{"name": "fat_finger_0.05", "enabled": false}
```

#### `GET /api/v1/risk/alerts`

取得歷史風控警報。支援分頁。

**查詢參數：**
- `limit`（整數，選用，預設 50，最大 200）：每頁筆數
- `offset`（整數，選用，預設 0）：跳過筆數

**回應** `200`：
```json
[
  {
    "timestamp": "2024-01-15T14:30:00",
    "rule_name": "max_position_weight_0.1",
    "severity": "WARNING",
    "metric_value": 0.12,
    "threshold": 0.10,
    "action_taken": "REJECTED",
    "message": "[AAPL] 預估權重 12.0% 超過上限 10.0%"
  }
]
```

#### `GET /api/v1/risk/realtime`

取得即時盤中回撤與分級警報（2%/3%/5%）。

**回應** `200`：
```json
{
  "intraday_drawdown": 0.012,
  "peak_nav": 10500000.0,
  "current_nav": 10374000.0,
  "alerts": [],
  "kill_switch_active": false
}
```

#### `PUT /api/v1/risk/config`

更新全域風控設定。

#### `PUT /api/v1/risk/rules/{rule_name}/config`

更新特定風控規則的參數設定。

#### `POST /api/v1/risk/kill-switch`

緊急熔斷：停止所有策略並取消所有掛單。

**回應** `200`：
```json
{
  "detail": "Kill switch activated",
  "code": "kill_switch"
}
```

---

### Alpha 研究

#### `POST /api/v1/alpha`

執行 Alpha 因子研究管線（universe 篩選 → 因子計算 → 中性化 → 正交化 → 複合訊號 → 分位回測）。

**請求主體：**
```json
{
  "universe": ["2330.TW", "2317.TW"],
  "factors": ["momentum_12_1", "ep"],
  "start": "2022-01-01",
  "end": "2024-12-31"
}
```

#### `GET /api/v1/alpha/{task_id}`

查詢 Alpha 研究任務狀態。

#### `GET /api/v1/alpha/{task_id}/result`

取得完整 Alpha 研究結果。

#### `GET /api/v1/alpha/regime`

取得當前市場狀態分類。

#### `POST /api/v1/alpha/ic-analysis`

IC（Information Coefficient）分析。

#### `POST /api/v1/alpha/turnover-analysis`

換手率分析。

#### `POST /api/v1/alpha/attribution`

績效歸因分析。

#### `POST /api/v1/alpha/factor-correlation`

因子相關性矩陣。

#### `POST /api/v1/alpha/neutralize`

因子中性化。

#### `POST /api/v1/alpha/filter-strategy`

條件式篩選策略（支援 13 種內建因子計算器）。

#### `POST /api/v1/alpha/event-rebalancer/test`

事件驅動再平衡回測。

---

### 資產配置

#### `POST /api/v1/allocation`

執行戰術資產配置（strategic weights + 宏觀因子 + 跨資產訊號 + 景氣判斷）。

**回應** `200`：回傳各 AssetClass 的目標權重。

#### `GET /api/v1/allocation/macro-factors`

取得宏觀因子（growth/inflation/rates/credit）的 FRED z-scores。

#### `GET /api/v1/allocation/cross-asset-signals`

取得跨資產訊號（momentum/volatility/value per AssetClass）。

---

### 執行

#### `GET /api/v1/execution/status`

取得執行服務狀態（模式、連線狀態等）。

#### `GET /api/v1/execution/market-hours`

取得當前交易時段資訊。

#### `POST /api/v1/execution/reconcile`

執行 EOD 持倉對帳。

#### `POST /api/v1/execution/reconcile/auto-correct`

自動修正對帳差異。

#### `GET /api/v1/execution/paper-trading/status`

取得模擬交易狀態。

#### `GET /api/v1/execution/queued-orders`

取得排隊中的訂單。

#### `GET /api/v1/execution/trading-limits`

取得交易限額資訊。

#### `GET /api/v1/execution/settlements`

取得結算資訊。

#### `GET /api/v1/execution/dispositions`

取得庫存明細。

#### `GET /api/v1/execution/stop-orders`

取得停損單列表。

#### `POST /api/v1/execution/stop-orders`

建立停損單。

#### `DELETE /api/v1/execution/stop-orders/{symbol}`

刪除特定標的停損單。

#### `DELETE /api/v1/execution/stop-orders`

清除所有停損單。

#### `POST /api/v1/execution/smart-order`

智慧拆單（TWAP 分割執行）。

#### `GET /api/v1/execution/reconciliation-history`

取得歷史對帳紀錄。

---

### Auto-Alpha

#### `GET /api/v1/auto-alpha/status`

取得 Auto-Alpha 排程器運行狀態。

#### `POST /api/v1/auto-alpha/start`

啟動 Auto-Alpha 排程器。

#### `POST /api/v1/auto-alpha/stop`

停止 Auto-Alpha 排程器。

#### `POST /api/v1/auto-alpha/run-now`

立即執行一輪 Auto-Alpha 研究週期。

#### `GET /api/v1/auto-alpha/run-now/{task_id}`

查詢 run-now 任務進度。

#### `GET /api/v1/auto-alpha/config`

取得 Auto-Alpha 設定。

#### `PUT /api/v1/auto-alpha/config`

更新 Auto-Alpha 設定。

#### `GET /api/v1/auto-alpha/history`

取得歷史快照列表。

#### `GET /api/v1/auto-alpha/history/{date}`

取得特定日期的快照詳情。

#### `GET /api/v1/auto-alpha/performance`

取得 Auto-Alpha 績效摘要。

#### `GET /api/v1/auto-alpha/alerts`

取得 Auto-Alpha 警報列表。

#### `GET /api/v1/auto-alpha/decision`

取得最新決策引擎輸出。

#### `GET /api/v1/auto-alpha/safety-gates`

取得安全閘門狀態。

#### `GET /api/v1/auto-alpha/factor-pnl`

取得因子損益歸因。

#### `GET /api/v1/auto-alpha/factor-pool`

取得動態因子池狀態。

---

### 策略中心

Web v2 專用端點，提供月營收選股策略的即時資訊。

#### `GET /api/v1/strategy/selection/latest`

取得最新一期月度選股結果。

#### `GET /api/v1/strategy/selection/history`

取得歷史選股紀錄。

#### `GET /api/v1/strategy/regime`

取得熊市偵測狀態與指標（MA200、波動率等）。

#### `GET /api/v1/strategy/drift`

取得目標 vs 實際持倉偏離度。

#### `POST /api/v1/strategy/rebalance`

一鍵觸發再平衡。

#### `GET /api/v1/strategy/data-status`

取得營收資料新鮮度。

#### `GET /api/v1/strategy/info`

取得策略基本資訊。

---

### 管理員

需要 `admin` 角色。

#### `GET /api/v1/admin/users`

列出所有使用者。

#### `POST /api/v1/admin/users`

建立使用者。

**請求主體：**
```json
{
  "username": "john",
  "display_name": "John",
  "password": "securePass123",
  "role": "trader"
}
```

#### `PUT /api/v1/admin/users/{user_id}`

修改使用者（角色、啟用狀態、顯示名稱）。

#### `DELETE /api/v1/admin/users/{user_id}`

刪除使用者。

#### `POST /api/v1/admin/users/{user_id}/reset-password`

重設使用者密碼。

---

## WebSocket

### 連線

```
ws://localhost:8000/ws/{channel}
```

**支援頻道：**

| 頻道 | 說明 |
|------|------|
| `portfolio` | 即時持倉與損益更新 |
| `alerts` | 風控警報通知 |
| `orders` | 訂單狀態變更通知 |
| `market` | 行情數據串流 |

### 連線範例

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/portfolio");

ws.onopen = () => {
  console.log("已連線");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("更新:", data);
};

// 心跳保活
setInterval(() => ws.send("ping"), 30000);
```

### 心跳機制

發送文字訊息 `"ping"`，伺服器回應 `"pong"`。

### 無效頻道

連線至不支援的頻道時，伺服器回傳 WebSocket 關閉碼 `4000`，原因為 `"Invalid channel: {name}"`。

---

## 錯誤回應

所有錯誤回應遵循此格式：

```json
{
  "detail": "錯誤描述",
  "code": "error"
}
```

### HTTP 狀態碼

| 狀態碼 | 含義 |
|--------|------|
| `200` | 成功 |
| `202` | 已接受（非同步任務已建立） |
| `401` | 認證無效或缺失 |
| `403` | 角色權限不足 |
| `404` | 資源未找到 |
| `429` | 請求過於頻繁（速率限制） |
| `500` | 伺服器內部錯誤 |
