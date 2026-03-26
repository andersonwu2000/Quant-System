# 量化交易系統架構設計 v3.0

> 核心轉向：從「展示架構能力」轉為「能被一個 2-5 人團隊長期維護的生產系統」。
> 新增重點：統一 API 契約、多平台 UI、開發者體驗。

---

## 一、設計哲學

### 1.1 v2 → v3 的反思

v2.0 犯了典型的架構天文學錯誤 (Architecture Astronaut)：

| v2 設計 | 問題 | v3 決策 |
|---------|------|---------|
| Event Sourcing + CQRS | 量化系統不是電商，寫入量有限，讀寫分離帶來的複雜度遠超收益 | **單一狀態模型** + append-only 交易日誌 |
| Circuit Breaker 模式 | 過度抽象；量化系統的外部依賴只有 2-3 個（行情源、券商），各自寫具體的重連邏輯更清晰 | **具體的重連策略**，不抽象 |
| mTLS / Zero-Trust | 量化系統是內網部署，不是公開 SaaS | **API Key + HTTPS** 即可 |
| 16 種事件型別 | 事件太碎，增加一個功能要改 5 個檔案 | **精簡為 6 種核心事件** |
| 進程級策略隔離 | 多進程 IPC 複雜度高，大多數團隊跑 3-5 個策略，不需要 | **執行緒級隔離** + 異常捕獲即可 |
| 分散式追蹤 (OpenTelemetry) | 單機系統不需要跨服務追蹤 | **結構化日誌** + request_id 串聯 |

### 1.2 v3 設計原則

```
1. 能用函式解決的不用類別
2. 能用單體解決的不用微服務
3. 能用 SQL 解決的不用自建存儲
4. 能用標準庫解決的不用框架
5. 每新增一層抽象，必須回答：「這個抽象讓哪個具體操作變簡單了？」
```

**量化金融面的原則不變**（這些是不可簡化的本質複雜度）：
- 時間因果性 / Look-ahead bias 防護
- 市場摩擦真實建模
- 統計嚴謹性 / 過擬合防護
- 風控獨立性

---

## 二、系統拓撲

### 2.1 部署架構：務實的單體 + 獨立前端

```
┌─────────────────────────────────────────────────────────────┐
│                     部署拓撲                                  │
│                                                             │
│   ┌───────────────────────────────────────────────┐         │
│   │          Trading Server (單體 Python 進程)      │         │
│   │                                               │         │
│   │  ┌─────────┐ ┌──────┐ ┌──────┐ ┌───────────┐ │         │
│   │  │ 數據引擎 │ │ 策略 │ │ 風控 │ │ 執行/OMS  │ │         │
│   │  └─────────┘ └──────┘ └──────┘ └───────────┘ │         │
│   │                    │                          │         │
│   │              ┌─────▼─────┐                    │         │
│   │              │  API 層    │                    │         │
│   │              │ FastAPI   │                    │         │
│   │              └─────┬─────┘                    │         │
│   └────────────────────┼──────────────────────────┘         │
│                        │                                    │
│          ┌─────────────┼──────────────┐                     │
│          │  REST/WS     │  REST/WS     │                    │
│          ▼             ▼              ▼                     │
│   ┌────────────┐ ┌──────────┐  ┌────────────┐              │
│   │  Web 前端   │ │ 桌面應用  │  │ 行動裝置    │              │
│   │  React     │ │ Tauri    │  │ React      │              │
│   │            │ │          │  │ Native     │              │
│   └────────────┘ └──────────┘  └────────────┘              │
│                                                             │
│   ┌───────────────────────────────────────────────┐         │
│   │        離線計算 (獨立進程，按需啟動)              │         │
│   │  回測引擎 · 因子批次計算 · 報表生成              │         │
│   └───────────────────────────────────────────────┘         │
│                                                             │
│   ┌───────────────────────────────────────────────┐         │
│   │              PostgreSQL                       │         │
│   │  行情 · 持倉 · 訂單 · 因子 · 配置 · 日誌        │         │
│   └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

**關鍵決策**：

| 決策 | 理由 |
|------|------|
| 交易引擎是單體 | 進程內呼叫延遲 < 1μs，IPC 延遲 > 100μs；策略數量 < 20 個，單機夠用 |
| 一個 PostgreSQL | 時序查詢用 TimescaleDB 擴展即可；不需要 Redis + Kafka + ClickHouse 三套系統 |
| 回測是獨立進程 | 回測 CPU 密集，不應與實盤交易搶資源；但共用同一份代碼和 DB |
| API 層內嵌於交易引擎 | 避免進程間通訊；FastAPI 的異步不會阻塞交易主循環 |
| 前端獨立部署 | 前後端分離是正確的，用同一套 API 契約服務所有平台 |

### 2.2 為什麼不用微服務

量化交易系統的流量特徵與 Web 應用截然不同：

```
Web 應用：百萬用戶、讀重寫輕、水平擴展、最終一致性可接受
量化系統：1-5 個用戶、讀寫均衡、垂直擴展、強一致性必要

微服務帶來的成本：
├── 網絡延遲（跨服務呼叫 vs 函式呼叫）
├── 分散式事務（下單 + 風控 + 持倉更新必須原子性）
├── 部署複雜度（5 個服務 × 3 個環境 = 15 個部署單元）
├── 除錯困難（一個 bug 可能橫跨 3 個服務的日誌）
└── 團隊開銷（2-5 人團隊無法有效維護微服務邊界）

結論：交易引擎是進程內單體，複雜度用模組邊界管理，不用服務邊界。
```

---

## 三、API 設計：多平台的統一契約

### 3.1 API 架構

API 層是整個系統最重要的邊界——它定義了「交易引擎能做什麼」的完整契約，
所有平台（Web、桌面、行動裝置、CLI、第三方整合）都通過同一套 API 操作系統。

```
┌──────────────────────────────────────────────────────────────┐
│                       API 層架構                              │
│                                                              │
│  ┌─ HTTP REST ──────────────────────────────────────────┐    │
│  │  CRUD 操作 · 查詢 · 命令                               │    │
│  │  GET  /api/v1/portfolio                              │    │
│  │  POST /api/v1/strategies/{id}/start                  │    │
│  │  GET  /api/v1/backtest/{id}/result                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ WebSocket ──────────────────────────────────────────┐    │
│  │  即時推送 · 雙向通訊                                    │    │
│  │  ws://host/ws/market      (即時行情)                   │    │
│  │  ws://host/ws/portfolio   (持倉/PnL 即時更新)          │    │
│  │  ws://host/ws/alerts      (風控告警)                   │    │
│  │  ws://host/ws/orders      (訂單狀態變更)               │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ 橫切 ──────────────────────────────────────────────┐    │
│  │  認證: API Key (Header) + JWT (Bearer Token)         │    │
│  │  版本: URL 路徑 (/api/v1/, /api/v2/)                 │    │
│  │  限流: 令牌桶 (100 req/s REST, 10 conn WS)           │    │
│  │  錯誤: RFC 7807 Problem Details 統一格式              │    │
│  │  分頁: Cursor-based (避免 OFFSET 效能問題)            │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 API 端點設計

```yaml
# ═══ 市場數據 ═══
GET    /api/v1/market/quotes/{symbol}          # 最新報價
GET    /api/v1/market/bars/{symbol}            # K 線 (?freq=1d&start=...&end=...)
GET    /api/v1/market/symbols                  # 可交易標的清單

# ═══ 投資組合 ═══
GET    /api/v1/portfolio                       # 當前持倉 + NAV + 曝險摘要
GET    /api/v1/portfolio/positions              # 逐筆持倉明細
GET    /api/v1/portfolio/pnl                    # PnL 歷史曲線 (?period=1d|1w|1m|ytd)
GET    /api/v1/portfolio/risk                   # 風險快照 (VaR, 曝險, Greeks)

# ═══ 策略管理 ═══
GET    /api/v1/strategies                      # 所有策略列表 + 狀態
GET    /api/v1/strategies/{id}                 # 單一策略詳情
POST   /api/v1/strategies/{id}/start           # 啟動策略
POST   /api/v1/strategies/{id}/stop            # 停止策略
PUT    /api/v1/strategies/{id}/params          # 更新策略參數 (風控範圍內)
GET    /api/v1/strategies/{id}/performance     # 策略績效

# ═══ 訂單 ═══
GET    /api/v1/orders                          # 訂單列表 (?status=open|filled|all)
GET    /api/v1/orders/{id}                     # 單筆訂單詳情
POST   /api/v1/orders                          # 手動下單 (需要 Trader 角色)
DELETE /api/v1/orders/{id}                     # 撤單

# ═══ 風控 ═══
GET    /api/v1/risk/rules                      # 風控規則列表
PUT    /api/v1/risk/rules/{id}                 # 修改規則參數 (需要 RiskManager 角色)
GET    /api/v1/risk/breaches                   # 風控觸發歷史
POST   /api/v1/risk/kill-switch                # 緊急熔斷 (需要 RiskManager 角色)

# ═══ 回測 ═══
POST   /api/v1/backtest                        # 提交回測任務 (異步，返回 task_id)
GET    /api/v1/backtest/{task_id}              # 查詢回測狀態與進度
GET    /api/v1/backtest/{task_id}/result        # 取得回測結果

# ═══ 因子研究 ═══
GET    /api/v1/factors                         # 因子庫列表
GET    /api/v1/factors/{name}/report           # 因子分析報告 (IC, 衰減, 相關性)
POST   /api/v1/factors/{name}/compute          # 觸發因子重新計算

# ═══ 系統 ═══
GET    /api/v1/system/health                   # 健康檢查
GET    /api/v1/system/status                   # 系統狀態 (連線, 延遲, 隊列)
GET    /api/v1/system/logs                     # 查詢日誌 (?level=WARNING&module=risk)
```

### 3.3 WebSocket 訊息協議

所有 WebSocket 訊息使用統一的信封格式：

```jsonc
// 客戶端 → 伺服器：訂閱
{ "type": "subscribe", "channel": "portfolio", "params": {} }

// 伺服器 → 客戶端：數據推送
{
  "type": "update",
  "channel": "portfolio",
  "timestamp": "2026-03-22T09:30:00.123Z",
  "data": {
    "nav": 10523400.50,
    "daily_pnl": 23400.50,
    "daily_pnl_pct": 0.0022,
    "positions_count": 15,
    "gross_exposure": 9800000.00,
    "net_exposure": 3200000.00
  }
}

// 伺服器 → 客戶端：告警推送
{
  "type": "alert",
  "channel": "alerts",
  "timestamp": "2026-03-22T10:15:32.456Z",
  "data": {
    "severity": "WARNING",
    "rule": "daily_drawdown_limit",
    "message": "日回撤達 2.1%，接近 3% 閾值",
    "metric_value": 0.021,
    "threshold": 0.03
  }
}
```

### 3.4 API 的多平台適配考量

```
                    ┌──────────────┐
                    │  API Server  │
                    │  (FastAPI)   │
                    └──────┬───────┘
                           │
          同一套 API，不同的消費模式
                           │
       ┌───────────┬───────┼────────┬────────────┐
       ▼           ▼       ▼        ▼            ▼
  ┌─────────┐ ┌────────┐ ┌─────┐ ┌───────┐ ┌─────────┐
  │ Web SPA │ │ 桌面   │ │ 行動│ │  CLI  │ │ 外部    │
  │ React   │ │ Tauri  │ │ App │ │ Tool  │ │ 整合    │
  └─────────┘ └────────┘ └─────┘ └───────┘ └─────────┘

  全功能     全功能     精簡版    腳本化     Webhook
  即時看板   系統通知   推播告警  自動化     第三方
  研究工具   低延遲     持倉速覽  批次操作   通知
```

**各平台的差異化設計**：

| 面向 | Web | 桌面 (Tauri) | 行動裝置 | CLI |
|------|-----|-------------|---------|-----|
| 首要用途 | 研究分析、回測、因子探索 | 交易監控、即時操作 | 告警通知、狀態速覽 | 自動化腳本、批次操作 |
| 數據量 | 完整 | 完整 | 摘要 | 按需 |
| 更新頻率 | 1-5 秒 | 100ms-1 秒 | 推播 + 手動刷新 | 一次性 |
| 離線能力 | 無 | 快取最近數據 | 快取最後快照 | 無 |
| 認證方式 | JWT (登入) | JWT (登入) | JWT + 生物辨識 | API Key |
| 關鍵互動 | 圖表互動、參數調整 | Kill Switch、策略控制 | 確認告警、緊急停止 | 啟停策略、查詢 |

### 3.5 SDK 生成策略

從 API 定義自動生成各平台的客戶端 SDK，而非手寫：

```
OpenAPI Spec (自動從 FastAPI 生成)
    │
    ├──→ TypeScript SDK  → Web 前端 / React Native
    ├──→ Rust SDK        → Tauri 桌面應用
    └──→ Python SDK      → CLI 工具 / Notebook 整合 / 第三方

好處：
- API 變更後，SDK 自動同步，不會前後端不一致
- 類型安全：前端拿到的是有型別的物件，不是 any
- 文件自動生成：Swagger UI / Redoc
```

---

## 四、多平台用戶介面

### 4.1 UI 分層架構

```
┌──────────────────────────────────────────────────────────────────┐
│                         UI 架構分層                                │
│                                                                  │
│  ┌─ 展示層 (Platform-Specific) ──────────────────────────────┐   │
│  │  Web: React + Tailwind + Recharts                         │   │
│  │  Desktop: Tauri + 同一套 React                             │   │
│  │  Mobile: React Native (精簡版)                             │   │
│  └────────────────────────┬──────────────────────────────────┘   │
│                           │                                      │
│  ┌─ 共享業務邏輯層 ────────┴──────────────────────────────────┐   │
│  │  TypeScript Package (@quant/core)                          │   │
│  │  ├── API Client (自動生成)                                  │   │
│  │  ├── WebSocket 管理 (自動重連、訂閱管理)                      │   │
│  │  ├── 狀態管理 (Zustand store)                               │   │
│  │  ├── 數據格式化 (金額、百分比、時間)                           │   │
│  │  └── 業務常數 (風控閾值顏色、策略狀態映射)                     │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

**關鍵**：三個平台共享一個 TypeScript 業務邏輯包。UI 元件各自實現，但數據流、狀態管理、API 呼叫完全共用。改一次業務邏輯，三個平台同步。

### 4.2 角色導向的介面設計

不同角色看到的不是同一個介面——這不只是權限控制，而是完全不同的信息架構：

```
┌─────────────────────────────────────────────────────────────┐
│ 研究員 (Researcher) — 主要使用 Web                            │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ 因子實驗室 │  │ 回測工作台    │  │ 數據瀏覽器             │  │
│  │          │  │              │  │                       │  │
│  │ 因子定義  │  │ 參數設定     │  │ 行情圖表              │  │
│  │ IC 分析  │  │ 即時進度     │  │ 基本面查詢            │  │
│  │ 相關性   │  │ 結果視覺化   │  │ 因子值視覺化           │  │
│  │ 衰減曲線  │  │ 歷史比較     │  │ 股票池管理            │  │
│  └──────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 交易員 (Trader) — 主要使用桌面應用                              │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  即時總覽 (永遠可見)                     │  │
│  │  NAV: $10.5M  │ 日PnL: +$23K (+0.22%)  │ 策略: 5/5 運行│ │
│  └───────────────────────────────────────────────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ 持倉監控  │  │ 訂單管理     │  │ 策略控制台             │  │
│  │          │  │              │  │                       │  │
│  │ 即時 PnL │  │ 掛單狀態     │  │ 啟動/停止             │  │
│  │ 曝險分解  │  │ 成交回報     │  │ 參數調整              │  │
│  │ 持倉熱圖  │  │ 手動下單     │  │ 即時信號值            │  │
│  └──────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 風控經理 (Risk Manager) — 桌面 + 行動裝置                     │
│                                                             │
│  ┌──────────────────────────┐  ┌────────────────────────┐   │
│  │ 風險儀表板                │  │ 風控規則管理            │   │
│  │                          │  │                        │   │
│  │ VaR 儀表盤 (即時)        │  │ 規則列表 + 參數編輯     │   │
│  │ 曝險分解 (行業/因子)     │  │ 觸發歷史               │   │
│  │ 壓力測試結果             │  │ Kill Switch 按鈕       │   │
│  │ 回撤走勢 + 閾值線        │  │ (需要二次確認)          │   │
│  └──────────────────────────┘  └────────────────────────┘   │
│                                                             │
│  行動裝置精簡版：                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  [即時告警推播]  →  [風險摘要卡片]  →  [緊急停止按鈕]  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Notebook 整合 (研究員的主要工作環境)

研究員大部分時間在 Jupyter Notebook 裡，UI 不應該強迫他們離開 Notebook：

```python
# 在 Notebook 中直接使用 Python SDK 操作系統
from quant_client import Client

client = Client("http://localhost:8000", api_key="...")

# 查詢因子表現
report = client.factors.get_report("momentum_12_1")
report.plot_ic_decay()        # 直接出圖

# 提交回測並等待結果
result = client.backtest.run(
    strategy="momentum_v3",
    start="2020-01-01",
    end="2025-12-31",
    params={"lookback": 20, "holding_period": 5},
)
result.plot_equity_curve()
result.plot_drawdown()
print(result.summary())       # Sharpe, 回撤, 換手率...

# 查看當前實盤持倉
portfolio = client.portfolio.get()
portfolio.to_dataframe()      # 直接轉 DataFrame 操作
```

---

## 五、核心引擎（簡化後）

### 5.1 領域模型 — 只保留真正需要的

v2 定義了過多的值物件。v3 的原則：**如果一個型別在兩個以上的模組邊界傳遞，才值得定義為獨立型別**。

```python
# domain/models.py — 整個領域模型在一個檔案，< 200 行

from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"

class AssetClass(Enum):
    EQUITY = "EQUITY"
    FUTURE = "FUTURE"
    OPTION = "OPTION"

class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass(frozen=True)
class Instrument:
    symbol: str                         # "2330.TW", "AAPL", "ESH5"
    asset_class: AssetClass
    currency: str                       # "TWD", "USD"
    lot_size: int = 1                   # 最小交易單位
    tick_size: Decimal = Decimal("0.01")
    multiplier: Decimal = Decimal("1")  # 期貨/選擇權合約乘數

@dataclass
class Position:
    instrument: Instrument
    quantity: Decimal                    # 正=多, 負=空
    avg_cost: Decimal
    market_price: Decimal = Decimal("0")

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.market_price * self.instrument.multiplier

    @property
    def unrealized_pnl(self) -> Decimal:
        return (self.market_price - self.avg_cost) * self.quantity * self.instrument.multiplier

@dataclass
class Order:
    id: str
    instrument: Instrument
    side: Side
    quantity: Decimal
    price: Decimal | None               # None = 市價單
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: Decimal = Decimal("0")
    filled_avg_price: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=datetime.utcnow)
    strategy_id: str = ""               # 來源策略
    client_order_id: str = ""           # 冪等鍵

@dataclass
class Portfolio:
    positions: dict[str, Position]      # key = symbol
    cash: Decimal
    as_of: datetime

    @property
    def nav(self) -> Decimal:
        return self.cash + sum(p.market_value for p in self.positions.values())

    @property
    def gross_exposure(self) -> Decimal:
        return sum(abs(p.market_value) for p in self.positions.values())
```

**v2 vs v3 對比**：
- v2: `Price`, `Quantity`, `Money`, `Bps`, `InstrumentId`, `Greeks` — 6 個值物件 + 貨幣安全運算
- v3: 用 `Decimal` + `str` 就夠了。除非你真的在做多幣種跨境交易，否則 `Money` 型別是過度設計
- v3: `Greeks` 等衍生品相關型別在需要時再加，不預先設計

### 5.2 模組邊界 — 用 Python Package 而非微服務

```
src/
├── domain/          # 領域模型（無外部依賴，純 Python）
│   └── models.py
│
├── data/            # 數據模組
│   ├── feed.py      # DataFeed: 即時行情 + 歷史數據的統一介面
│   ├── store.py     # 數據存取層 (PostgreSQL)
│   └── quality.py   # 數據品質檢查
│
├── strategy/        # 策略模組
│   ├── base.py      # Strategy 基類 (唯一需要繼承的抽象)
│   ├── engine.py    # 策略調度器
│   ├── factors.py   # 因子計算 (純函數)
│   └── optimizer.py # 投資組合優化
│
├── risk/            # 風控模組
│   ├── engine.py    # 風控引擎
│   ├── rules.py     # 所有風控規則 (一個檔案，用聲明式配置)
│   └── monitor.py   # 即時監控
│
├── execution/       # 執行模組
│   ├── oms.py       # 訂單管理
│   ├── broker.py    # 券商介面 + 實現
│   └── sim.py       # 模擬撮合 (回測 + 紙上交易共用)
│
├── api/             # API 模組
│   ├── app.py       # FastAPI application
│   ├── routes/      # 路由定義 (按資源分檔)
│   ├── ws.py        # WebSocket 管理
│   ├── auth.py      # 認證與授權
│   └── schemas.py   # Pydantic 請求/回應模型 (→ OpenAPI spec)
│
├── backtest/        # 回測模組 (獨立進程)
│   ├── engine.py    # 回測引擎
│   ├── analytics.py # 績效分析
│   └── validation.py# 回測嚴謹性檢查
│
└── cli/             # 命令列工具
    └── main.py      # CLI 入口 (Typer)
```

**模組間依賴規則**（由內而外，單向依賴）：

```
domain  ←──  data
domain  ←──  strategy  ←──  data
domain  ←──  risk
domain  ←──  execution
domain  ←──  backtest  ←──  strategy, risk, execution/sim
所有模組 ←──  api (API 層是最外層，依賴所有內層)
```

**禁止的依賴**：
- `strategy` 不得直接依賴 `execution`（策略產出信號，不操作訂單）
- `risk` 不得依賴 `strategy`（風控獨立於策略）
- `domain` 不得依賴任何其他模組

### 5.3 策略介面 — 只有一個抽象類別

v2 有 `Strategy`, `Factor`, `PortfolioOptimizer`, `SlippageModel`, `ExecutionAlgo` 五個抽象。
v3 只暴露一個必須繼承的介面，其餘用組合：

```python
# strategy/base.py

class Strategy(ABC):
    """
    唯一需要繼承的類別。

    設計決策：
    - on_bar 返回目標權重 dict，不是訂單。
      系統自動計算 diff → 風控檢查 → 生成訂單。
      策略作者不需要關心訂單管理。
    - context 提供所有需要的數據和工具，策略不直接碰 DB 或網路。
    """

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def on_bar(self, ctx: Context) -> dict[str, float]:
        """
        收到新的 bar 數據，返回目標持倉權重。

        Args:
            ctx: 提供歷史數據、當前持倉、風險指標的上下文

        Returns:
            {"2330.TW": 0.05, "2317.TW": 0.03, ...}
            權重 = 佔 NAV 比例，正=多頭，負=空頭
            不在 dict 中的標的 = 目標權重為 0 (即平倉)

        約束：
            - 只能使用 ctx 提供的數據 (時間因果性由 ctx 保證)
            - 返回值是純粹的「意圖」，風控可能修改或拒絕
        """


class Context:
    """策略的唯一數據入口——回測和實盤提供相同的介面。"""

    def bars(self, symbol: str, lookback: int = 252) -> pd.DataFrame:
        """取得歷史 K 線 (OHLCV)。回測時自動截斷到當前模擬時間。"""

    def universe(self) -> list[str]:
        """當前可交易標的清單。"""

    def portfolio(self) -> Portfolio:
        """當前持倉快照。"""

    def now(self) -> datetime:
        """當前時間。回測時是模擬時間，實盤是實際時間。"""

    def log(self, msg: str, **kwargs) -> None:
        """結構化日誌。"""
```

**一個完整策略只需要 20 行**：

```python
class MomentumStrategy(Strategy):
    def name(self) -> str:
        return "momentum_12_1"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        weights = {}
        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=252)
            if len(bars) < 252:
                continue
            # 12 個月動量，跳過最近 1 個月
            ret = bars["close"].iloc[-21] / bars["close"].iloc[-252] - 1
            weights[symbol] = ret

        # 正規化為目標權重
        if weights:
            total = sum(abs(v) for v in weights.values())
            weights = {k: v / total * 0.95 for k, v in weights.items()}  # 95% 投資
        return weights
```

### 5.4 風控 — 聲明式規則，不需要繼承

```python
# risk/rules.py — 所有規則在一個檔案，純函式 + 配置

@dataclass
class RiskRule:
    name: str
    check: Callable[[Order, Portfolio, MarketState], RiskDecision]
    enabled: bool = True

def max_position_weight(threshold: float = 0.05) -> RiskRule:
    """單一標的權重上限。"""
    def check(order, portfolio, market):
        projected = _project_position(order, portfolio)
        weight = abs(projected) / portfolio.nav
        if weight > threshold:
            return RiskDecision.REJECT(f"{order.instrument.symbol} 權重 {weight:.1%} > {threshold:.1%}")
        return RiskDecision.APPROVE()
    return RiskRule(f"max_position_weight_{threshold}", check)

def daily_drawdown_limit(threshold: float = 0.03) -> RiskRule:
    """日回撤上限。"""
    def check(order, portfolio, market):
        if portfolio.daily_drawdown > threshold:
            return RiskDecision.REJECT(f"日回撤 {portfolio.daily_drawdown:.1%} > {threshold:.1%}")
        return RiskDecision.APPROVE()
    return RiskRule(f"daily_drawdown_{threshold}", check)

# 風控配置：一目了然
DEFAULT_RULES = [
    max_position_weight(0.05),
    max_sector_weight(0.20),
    daily_drawdown_limit(0.03),
    weekly_drawdown_limit(0.10),
    fat_finger_check(0.05),
    max_daily_trades(100),
    max_order_size_vs_adv(0.10),
]
```

### 5.5 回測 — 與實盤同構的關鍵

```python
# backtest/engine.py

class BacktestEngine:
    """
    回測 = 用歷史數據驅動同一份策略代碼。

    核心保證：
    1. Context 在時刻 t 只暴露 ≤ t 的數據（SimContext 實現）
    2. 成交模擬包含滑價和手續費
    3. 相同參數 → 相同結果（確定性）
    """

    def run(self, strategy: Strategy, config: BacktestConfig) -> BacktestResult:
        sim_context = SimContext(config.universe, config.start, config.end)
        sim_broker = SimBroker(
            slippage_bps=config.slippage_bps,
            commission_rate=config.commission_rate,
        )
        risk_engine = RiskEngine(config.risk_rules or DEFAULT_RULES)
        portfolio = Portfolio(positions={}, cash=config.initial_cash, as_of=config.start)

        daily_returns = []
        for bar_date in sim_context.trading_dates():
            sim_context.advance_to(bar_date)
            target_weights = strategy.on_bar(sim_context)
            orders = _weights_to_orders(target_weights, portfolio)
            approved = [o for o in orders if risk_engine.check(o, portfolio).approved]
            fills = sim_broker.execute(approved, sim_context.current_bars())
            portfolio = _apply_fills(portfolio, fills)
            daily_returns.append(_calc_daily_return(portfolio))

        return BacktestResult(
            daily_returns=pd.Series(daily_returns),
            trades=sim_broker.trade_log,
            final_portfolio=portfolio,
        )
```

---

## 六、工程支持能力

### 6.1 開發者體驗 (DX)

```
┌──────────────────────────────────────────────────────────────┐
│                   開發者日常工作流                               │
│                                                              │
│  $ quant init my-strategy       # 腳手架：生成策略模板         │
│  $ quant backtest my-strategy   # 一鍵回測                    │
│  $ quant paper my-strategy      # 切換到紙上交易               │
│  $ quant live my-strategy       # 上線（需確認）               │
│  $ quant status                 # 所有策略的即時狀態            │
│  $ quant logs --strategy mom    # 查看特定策略日誌              │
│  $ quant factor report mom_12_1 # 因子分析報告                 │
│  $ quant kill                   # 緊急停止所有策略              │
└──────────────────────────────────────────────────────────────┘
```

CLI 工具 (基於 Typer) 是高級用戶和自動化腳本的入口，底層呼叫同一套 API。

### 6.2 本地開發環境

```yaml
# docker-compose.yaml — 一個指令啟動完整環境
services:
  db:
    image: timescale/timescaledb:latest-pg16
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  server:
    build: .
    ports: ["8000:8000"]
    depends_on: [db]
    volumes: [./src:/app/src]           # 熱重載
    environment:
      - MODE=development
      - DATABASE_URL=postgresql://...

  web:
    build: ./frontend/web
    ports: ["3000:3000"]
    volumes: [./frontend/web/src:/app/src]  # 熱重載

volumes:
  pgdata:
```

```bash
# 新成員 Day 1：
git clone <repo>
docker compose up
# 完成。DB 自動 migration，測試數據自動載入。
```

### 6.3 測試策略

```
測試金字塔：

         ┌──────────┐
         │  E2E     │  少量：完整回測跑一個已知策略，驗證結果不變
         │ (回測驗證)│
        ┌┴──────────┴┐
        │ 整合測試    │  中量：API 端點 + DB 交互
        │ (API + DB) │
       ┌┴────────────┴┐
       │   單元測試     │  大量：領域模型、因子計算、風控規則
       │  (純函式)     │
       └──────────────┘
```

**特殊測試需求**：

| 測試類型 | 目的 | 實現 |
|---------|------|------|
| 因果性檢查 | 策略是否偷看未來數據 | 打亂時間軸後結果應變差；對 Context 注入 spy |
| 確定性檢查 | 同參數回測結果是否一致 | 跑兩次，逐日比對 returns |
| 性質測試 | 持倉 + 現金 = NAV 恆成立 | Hypothesis 生成隨機操作序列 |
| 滑價敏感度 | 策略在高滑價下是否仍盈利 | 參數掃描 slippage_bps = [1, 5, 10, 20, 50] |

### 6.4 部署與發布

```
開發流程：
                                        ┌─ 回測基準不退化
feature branch ──→ PR ──→ CI 檢查 ──────┤─ 單元/整合測試通過
                                        ├─ 型別檢查 (mypy)
                                        └─ 程式碼風格 (ruff)
    │
    ▼
merge to main ──→ 自動部署到 staging ──→ 紙上交易驗證 (≥ 1 週)
    │
    ▼ (手動觸發)
tag release ──→ 部署到 production
    │
    └── 回滾：git revert + 重新部署（< 5 分鐘）
```

**策略上線流程**（量化特有）：

```
策略生命週期：
研究 → 回測通過 → Code Review → 紙上交易 (4週+) → 小額實盤 → 逐步放量
                                    │
                                    └── 每個階段有明確的通過標準：
                                        紙上交易：Sharpe > 1.0, 最大回撤 < 10%
                                        小額實盤：滑價 < 預期 × 1.5
                                        放量：TCA 持續監控
```

### 6.5 配置管理

```python
# config.py — Pydantic Settings，一目了然，型別安全

class TradingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QUANT_")

    # 運行模式
    mode: Literal["backtest", "paper", "live"] = "backtest"

    # 數據庫
    database_url: str = "postgresql://localhost/quant"

    # 行情源
    data_source: Literal["yahoo", "fubon", "twse"] = "yahoo"

    # 風控
    max_position_pct: float = 0.05
    max_daily_drawdown_pct: float = 0.03
    kill_switch_weekly_drawdown_pct: float = 0.10

    # 執行
    default_slippage_bps: float = 5.0
    commission_rate: float = 0.001425    # 台灣券商手續費

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = ""                    # 生產環境必須設定

    # 日誌
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"
```

環境切換：用環境變數覆寫，不用多份 YAML。

```bash
# 開發
QUANT_MODE=backtest python -m quant

# 紙上交易
QUANT_MODE=paper QUANT_DATA_SOURCE=fubon python -m quant

# 生產
QUANT_MODE=live QUANT_DATA_SOURCE=fubon QUANT_API_KEY=xxx python -m quant
```

---

## 七、資料庫設計

一個 PostgreSQL + TimescaleDB 擴展，取代 v2 的四套存儲系統：

```sql
-- ═══ 行情數據 (TimescaleDB hypertable) ═══
CREATE TABLE bars (
    symbol      TEXT NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL,
    freq        TEXT NOT NULL,           -- '1m', '5m', '1d'
    open        NUMERIC NOT NULL,
    high        NUMERIC NOT NULL,
    low         NUMERIC NOT NULL,
    close       NUMERIC NOT NULL,
    volume      NUMERIC NOT NULL,
    PRIMARY KEY (symbol, timestamp, freq)
);
SELECT create_hypertable('bars', 'timestamp');

-- ═══ 交易記錄 (append-only，替代 Event Sourcing) ═══
CREATE TABLE trades (
    id              BIGSERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL,
    strategy_id     TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,        -- 'BUY' / 'SELL'
    quantity        NUMERIC NOT NULL,
    price           NUMERIC NOT NULL,
    commission      NUMERIC NOT NULL,
    slippage_bps    NUMERIC,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 數據血緣：這筆交易源自哪個信號
    signal_value    NUMERIC,
    signal_timestamp TIMESTAMPTZ
);

-- ═══ 持倉快照 (每日收盤後快照) ═══
CREATE TABLE position_snapshots (
    snapshot_date   DATE NOT NULL,
    symbol          TEXT NOT NULL,
    quantity        NUMERIC NOT NULL,
    avg_cost        NUMERIC NOT NULL,
    market_price    NUMERIC NOT NULL,
    market_value    NUMERIC NOT NULL,
    unrealized_pnl  NUMERIC NOT NULL,
    strategy_id     TEXT,
    PRIMARY KEY (snapshot_date, symbol)
);

-- ═══ 因子值 ═══
CREATE TABLE factor_values (
    factor_name     TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    value           NUMERIC NOT NULL,
    PRIMARY KEY (factor_name, symbol, date)
);

-- ═══ 回測結果 ═══
CREATE TABLE backtest_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name   TEXT NOT NULL,
    config          JSONB NOT NULL,      -- 完整參數快照
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL,        -- 'running', 'completed', 'failed'
    -- 摘要指標 (完整結果存 JSONB)
    sharpe          NUMERIC,
    max_drawdown    NUMERIC,
    total_return    NUMERIC,
    detail          JSONB                -- 完整每日收益序列等
);

-- ═══ 風控事件日誌 ═══
CREATE TABLE risk_events (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rule_name       TEXT NOT NULL,
    severity        TEXT NOT NULL,
    metric_value    NUMERIC,
    threshold       NUMERIC,
    action_taken    TEXT NOT NULL,
    detail          JSONB
);

-- ═══ 系統日誌 (結構化) ═══
CREATE TABLE system_logs (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level           TEXT NOT NULL,
    module          TEXT NOT NULL,
    message         TEXT NOT NULL,
    context         JSONB,               -- strategy_id, order_id 等
    request_id      TEXT                  -- 串聯同一操作的所有日誌
);
SELECT create_hypertable('system_logs', 'timestamp');
```

**v2 vs v3 存儲對比**：

| v2 | v3 | 簡化理由 |
|----|-----|---------|
| Redis (快取) + TimescaleDB (時序) + PostgreSQL (關聯) + Kafka (事件) + Parquet (冷存) | **PostgreSQL + TimescaleDB 一套** | 單機足以處理 < 1000 標的的行情量；TimescaleDB 的壓縮和查詢效能已夠用 |
| Event Store (append-only log) | **trades 表 + position_snapshots 表** | 交易記錄天然是 append-only；快照支持任意日期狀態重建 |
| Ring Buffer (進程內) | **Python dict** | 當日行情量在記憶體中就是幾百 MB |

---

## 八、目錄結構 (完整)

```
quant-trading-system/
│
├── pyproject.toml                         # 依賴管理 (uv/poetry)
├── docker-compose.yaml                    # 一鍵啟動開發環境
├── Makefile                               # 常用命令入口
├── .env.example                           # 環境變數模板
│
├── src/
│   ├── domain/
│   │   └── models.py                      # 領域模型 (< 200 行)
│   │
│   ├── data/
│   │   ├── feed.py                        # DataFeed 介面 + 即時/歷史實現
│   │   ├── store.py                       # DB 存取 (SQLAlchemy)
│   │   ├── quality.py                     # 數據品質檢查
│   │   └── sources/
│   │       ├── yahoo.py                   # Yahoo Finance (開發用)
│   │       └── fubon.py                   # 富邦 API (生產用)
│   │
│   ├── strategy/
│   │   ├── base.py                        # Strategy ABC + Context
│   │   ├── engine.py                      # 策略調度器
│   │   ├── factors.py                     # 因子函式庫
│   │   └── optimizer.py                   # 投資組合優化 (CVXPY)
│   │
│   ├── risk/
│   │   ├── engine.py                      # 風控引擎
│   │   ├── rules.py                       # 風控規則 (聲明式)
│   │   └── monitor.py                     # 即時監控 + 告警
│   │
│   ├── execution/
│   │   ├── oms.py                         # 訂單管理
│   │   ├── broker.py                      # 券商介面
│   │   └── sim.py                         # 模擬撮合
│   │
│   ├── backtest/
│   │   ├── engine.py                      # 回測引擎
│   │   ├── analytics.py                   # Sharpe, 回撤, 歸因...
│   │   └── validation.py                  # 因果性/確定性檢查
│   │
│   ├── api/
│   │   ├── app.py                         # FastAPI app + middleware
│   │   ├── routes/
│   │   │   ├── portfolio.py
│   │   │   ├── strategies.py
│   │   │   ├── orders.py
│   │   │   ├── risk.py
│   │   │   ├── backtest.py
│   │   │   ├── factors.py
│   │   │   ├── market.py
│   │   │   └── system.py
│   │   ├── ws.py                          # WebSocket 管理
│   │   ├── auth.py                        # 認證 + RBAC
│   │   └── schemas.py                     # Pydantic 模型 → OpenAPI
│   │
│   ├── cli/
│   │   └── main.py                        # Typer CLI
│   │
│   └── config.py                          # Pydantic Settings
│
├── frontend/
│   ├── packages/
│   │   └── core/                          # 共享業務邏輯 (TypeScript)
│   │       ├── src/
│   │       │   ├── api-client/            # 自動生成的 API client
│   │       │   ├── ws-manager.ts          # WebSocket 連線管理
│   │       │   ├── stores/                # Zustand 狀態管理
│   │       │   └── formatters.ts          # 金額/百分比/時間格式化
│   │       └── package.json
│   │
│   ├── web/                               # Web SPA (React)
│   │   ├── src/
│   │   │   ├── pages/                     # 研究員/交易員/風控 三組頁面
│   │   │   ├── components/                # UI 元件
│   │   │   └── App.tsx
│   │   └── package.json
│   │
│   ├── desktop/                           # 桌面應用 (Tauri + React)
│   │   ├── src-tauri/                     # Rust 後端 (系統通知等)
│   │   ├── src/                           # 復用 web 元件 + 桌面特有 UI
│   │   └── package.json
│   │
│   └── mobile/                            # 行動應用 (React Native)
│       ├── src/
│       │   ├── screens/                   # 精簡版頁面
│       │   └── components/
│       └── package.json
│
├── strategies/                            # 使用者的策略 (獨立於系統)
│   ├── momentum.py
│   ├── mean_reversion.py
│   └── stat_arb.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── backtest_validation/
│
├── migrations/                            # Alembic DB migrations
│   └── versions/
│
├── scripts/
│   ├── seed_data.py                       # 載入測試數據
│   └── generate_sdk.py                    # 從 OpenAPI 生成客戶端 SDK
│
└── notebooks/                             # 研究用 Jupyter Notebook
```

---

## 九、開發路線圖

```
Phase 0 — 地基 (2 週)
├── 領域模型 + DB schema + migration
├── 配置體系 (Pydantic Settings)
├── Docker Compose 開發環境
└── 交付物：docker compose up 後有空的系統框架

Phase 1 — 能跑回測 (4 週)
├── 數據：Yahoo Finance 數據源 + 數據存取層
├── 策略：Strategy ABC + Context + 一個示範策略
├── 回測：BacktestEngine + SimBroker + 績效分析
├── CLI：quant backtest 命令
└── 交付物：能對台股跑動量策略回測，產出 Sharpe/回撤報告

Phase 2 — 有 API 和基礎 UI (3 週)
├── API：FastAPI + 核心端點 (portfolio, strategies, backtest)
├── 前端共享層：@quant/core + API client 自動生成
├── Web 前端：回測結果頁 + 因子分析頁
├── 認證：API Key + JWT
└── 交付物：在瀏覽器中提交回測、查看結果

Phase 3 — 風控 + 紙上交易 (3 週)
├── 風控引擎 + 聲明式規則
├── 即時行情接入 (一個數據源)
├── PaperBroker (用即時行情模擬成交)
├── WebSocket 推送 (持倉/PnL/告警)
├── Web 前端：交易員看板 + 風控看板
└── 交付物：策略在模擬盤上跑，能即時看到持倉和 PnL

Phase 4 — 實盤 (4 週)
├── 券商 Adapter (對接一家)
├── OMS 完整流程
├── 對帳機制
├── Kill Switch (API + UI)
├── 桌面應用 (Tauri 封裝)
└── 交付物：一個策略在實盤小額運行

Phase 5 — 打磨 (持續)
├── 行動裝置 App (告警 + 狀態速覽)
├── 投資組合優化器 (CVXPY)
├── TCA 分析
├── 多策略資金分配
├── 績效歸因
└── 因子庫擴充
```

---

## 十、v2 → v3 刪除清單

明確記錄刪掉了什麼以及為什麼，避免未來有人重新發明：

| 刪除項 | 為什麼刪 | 如果未來需要 |
|--------|---------|-------------|
| Event Sourcing | 交易日誌 + 每日快照已夠用；事件溯源的 schema evolution 維護成本高 | 當監管要求逐筆重建歷史狀態時再引入 |
| CQRS | 讀寫量都不大，分離增加複雜度 | 當 API 讀取成為效能瓶頸時考慮 |
| Circuit Breaker | 外部依賴少，具體重連邏輯更清晰 | 當對接 > 5 個外部服務時考慮 |
| mTLS / Zero-Trust | 內網部署，HTTPS + API Key 夠用 | 當部署到公有雲或多租戶時引入 |
| 分散式追蹤 | 單體不需要跨服務追蹤 | 當拆分為微服務時引入 |
| Redis | PostgreSQL + 進程內 dict 夠快 | 當需要多進程共享快取時引入 |
| Kafka | 交易引擎是單體，不需要進程間消息隊列 | 當需要多個獨立消費者時引入 |
| 進程級策略隔離 | 2-5 人團隊跑 < 20 個策略，執行緒級夠用 | 當策略數量 > 50 或需要獨立資源限制時引入 |
| Greeks / 選擇權支持 | 先做好股票 + 期貨，衍生品之後再加 | Phase 5+ |
| 5 個 ABC (策略/因子/優化器/滑價/執行) | 過度抽象，只有 Strategy 需要繼承 | 當子類別 > 3 個時才值得抽象 |
