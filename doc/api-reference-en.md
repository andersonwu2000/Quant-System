# Quant Trading System — API Reference

## Overview

- **Base URL:** `http://localhost:8000`
- **API prefix:** `/api/v1`
- **Interactive docs:** `/docs` (Swagger UI), `/redoc` (ReDoc)
- **Content type:** `application/json`

## Authentication

### API Key

Include the `X-API-Key` header in every request:

```
X-API-Key: your-api-key
```

### JWT Token

Alternatively, use JWT Bearer token authentication:

```
Authorization: Bearer <jwt-token>
```

JWT tokens are created with `create_jwt_token(subject, role)` and contain a role claim. Tokens expire after 24 hours (configurable via `QUANT_JWT_EXPIRE_MINUTES`).

### Role Hierarchy

| Role | Level | Permissions |
|------|-------|-------------|
| `viewer` | 0 | Read-only access |
| `researcher` | 1 | + backtest |
| `trader` | 2 | + order management, strategy control |
| `risk_manager` | 3 | + risk rule management, kill switch |
| `admin` | 4 | Full access |

Higher roles inherit all permissions of lower roles.

---

## REST Endpoints

### System

#### `GET /api/v1/system/health`

Health check. **No authentication required.**

**Response** `200`:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

#### `GET /api/v1/system/status`

System status overview.

**Response** `200`:
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

### Portfolio

#### `GET /api/v1/portfolio`

Get full portfolio snapshot.

**Response** `200`:
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

Get list of open positions.

**Response** `200`:
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

### Strategies

#### `GET /api/v1/strategies`

List all registered strategies.

**Response** `200`:
```json
{
  "strategies": [
    {"name": "momentum_12_1", "status": "running", "pnl": 25000.0},
    {"name": "mean_reversion", "status": "stopped", "pnl": 0.0}
  ]
}
```

#### `GET /api/v1/strategies/{strategy_id}`

Get details for a specific strategy.

**Path parameters:**
- `strategy_id` (string): Strategy name

**Response** `200`:
```json
{"name": "momentum_12_1", "status": "running", "pnl": 25000.0}
```

**Response** `404`:
```json
{"detail": "Strategy not found: unknown_strategy", "code": "error"}
```

#### `POST /api/v1/strategies/{strategy_id}/start`

Start a strategy.

**Request body** (optional):
```json
{"params": {"lookback": 252}}
```

**Response** `200`:
```json
{"name": "momentum_12_1", "status": "running", "pnl": 0.0}
```

#### `POST /api/v1/strategies/{strategy_id}/stop`

Stop a running strategy.

**Response** `200`:
```json
{"name": "momentum_12_1", "status": "stopped", "pnl": 25000.0}
```

---

### Orders

#### `GET /api/v1/orders`

List orders with optional status filter.

**Query parameters:**
- `status` (string, optional): Filter by status — `"open"` or `"filled"`

**Response** `200`:
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

### Backtest

#### `POST /api/v1/backtest`

Submit an asynchronous backtest task.

**Request body:**
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

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | string | required | Strategy name |
| `universe` | string[] | required | Stock symbols |
| `start` | string | `"2020-01-01"` | Start date (YYYY-MM-DD) |
| `end` | string | `"2025-12-31"` | End date (YYYY-MM-DD) |
| `initial_cash` | float | `10000000.0` | Initial capital |
| `params` | object | `{}` | Strategy-specific parameters |
| `slippage_bps` | float | `5.0` | Slippage in basis points |
| `commission_rate` | float | `0.001425` | Commission rate |
| `rebalance_freq` | string | `"weekly"` | `"daily"`, `"weekly"`, `"monthly"` |

**Response** `202`:
```json
{
  "task_id": "bt-abc123",
  "status": "running",
  "strategy_name": "momentum"
}
```

#### `GET /api/v1/backtest/{task_id}`

Query backtest status and summary.

**Response** `200` (running):
```json
{
  "task_id": "bt-abc123",
  "status": "running",
  "strategy_name": "momentum"
}
```

**Response** `200` (completed):
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

**Response** `200` (failed):
```json
{
  "task_id": "bt-abc123",
  "status": "failed",
  "strategy_name": "momentum"
}
```

#### `GET /api/v1/backtest/{task_id}/result`

Get full backtest result with complete metrics.

**Response** `200`:
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

### Risk

#### `GET /api/v1/risk/rules`

List all risk rules and their enabled status.

**Response** `200`:
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

Toggle a risk rule on or off.

**Request body:**
```json
{"enabled": false}
```

**Response** `200`:
```json
{"name": "fat_finger_0.05", "enabled": false}
```

#### `GET /api/v1/risk/alerts`

Get historical risk alerts.

**Response** `200`:
```json
[
  {
    "timestamp": "2024-01-15T14:30:00",
    "rule_name": "max_position_weight_0.1",
    "severity": "WARNING",
    "metric_value": 0.12,
    "threshold": 0.10,
    "action_taken": "REJECTED",
    "message": "[AAPL] projected weight 12.0% exceeds limit 10.0%"
  }
]
```

#### `POST /api/v1/risk/kill-switch`

Emergency shutdown: stop all strategies and cancel all pending orders.

**Response** `200`:
```json
{
  "detail": "Kill switch activated",
  "code": "kill_switch"
}
```

---

## WebSocket

### Connection

```
ws://localhost:8000/ws/{channel}
```

**Supported channels:**

| Channel | Description |
|---------|-------------|
| `portfolio` | Real-time position and PnL updates |
| `alerts` | Risk alert notifications |
| `orders` | Order status change notifications |
| `market` | Market data streaming |

### Connection Example

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/portfolio");

ws.onopen = () => {
  console.log("Connected");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Update:", data);
};

// Keepalive
setInterval(() => ws.send("ping"), 30000);
```

### Keepalive

Send `"ping"` as text message; the server responds with `"pong"`.

### Invalid Channel

Attempting to connect to an unsupported channel returns WebSocket close code `4000` with reason `"Invalid channel: {name}"`.

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Description of the error",
  "code": "error"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `202` | Accepted (async task created) |
| `401` | Invalid or missing authentication |
| `403` | Insufficient role permissions |
| `404` | Resource not found |
| `500` | Internal server error |
