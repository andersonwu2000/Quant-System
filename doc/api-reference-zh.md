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

JWT Token 透過 `create_jwt_token(subject, role)` 建立，包含角色宣告。Token 預設 24 小時後過期（可透過 `QUANT_JWT_EXPIRE_MINUTES` 設定）。

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

## REST 端點

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

列出訂單，可按狀態篩選。

**查詢參數：**
- `status`（字串，選用）：按狀態篩選 — `"open"` 或 `"filled"`

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
  "strategy_name": "momentum"
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
  "strategy_name": "momentum"
}
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

取得歷史風控警報。

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
| `500` | 伺服器內部錯誤 |
