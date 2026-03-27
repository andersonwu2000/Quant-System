# 自動化量化交易系統架構

## 系統總覽

```
┌─────────────────────────────────────────────────────────────────┐
│                      Quant Trading System                       │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│  Data    │ Strategy │  Risk    │ Execution│   Monitoring        │
│  Engine  │  Engine  │  Engine  │  Engine  │   & Dashboard       │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴──────────┬──────────┘
     │          │          │          │                 │
┌────▼──────────▼──────────▼──────────▼─────────────────▼──────────┐
│                     Core Infrastructure                          │
│         (Message Bus / Event Loop / State Store)                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 模組架構

### 1. Data Engine（資料引擎）

負責所有市場資料的取得、清洗、儲存。

```
data_engine/
├── collectors/          # 資料收集器
│   ├── realtime.py      # 即時行情（Shioaji Tick/BidAsk 串流）
│   ├── historical.py    # 歷史 K 線 / Tick 下載
│   └── fundamental.py   # 基本面資料（財報、法人買賣超）
├── processors/          # 資料處理
│   ├── cleaner.py       # 資料清洗、補缺值
│   ├── normalizer.py    # 標準化格式
│   └── feature_eng.py   # 特徵工程（技術指標計算）
├── storage/             # 資料儲存
│   ├── timeseries.py    # 時序資料庫介面（InfluxDB / TimescaleDB）
│   └── cache.py         # Redis 快取（即時報價）
└── feeds.py             # 統一資料 Feed 介面
```

**關鍵設計：**
- 即時行情與歷史資料使用統一的 `MarketData` 資料結構
- 所有資料經過 `processors` 清洗後才進入策略引擎
- 支援 replay 模式：回測時用歷史資料模擬即時串流

---

### 2. Strategy Engine（策略引擎）

策略的開發、回測、與即時執行。

```
strategy_engine/
├── base.py              # 策略基底類別 (abstract)
├── strategies/          # 策略實作
│   ├── momentum.py      # 動量策略
│   ├── mean_revert.py   # 均值回歸
│   ├── pairs.py         # 配對交易
│   ├── ml_signal.py     # ML 模型訊號策略
│   └── composite.py     # 組合策略（多策略加權）
├── signals/             # 訊號產生器
│   ├── technical.py     # 技術指標訊號
│   ├── volume.py        # 量能訊號
│   └── sentiment.py     # 情緒面訊號
├── backtest/            # 回測框架
│   ├── engine.py        # 回測引擎
│   ├── metrics.py       # 績效指標（Sharpe, MDD, Win Rate...）
│   └── report.py        # 回測報告產生器
└── optimizer/           # 參數優化
    ├── grid_search.py   # 網格搜尋
    └── bayesian.py      # 貝葉斯優化
```

**策略基底類別介面：**

```python
class Strategy(ABC):
    @abstractmethod
    def on_market_data(self, data: MarketData) -> list[Signal]:
        """收到新的市場資料時觸發，回傳交易訊號"""
        ...

    @abstractmethod
    def on_order_update(self, order: OrderUpdate) -> None:
        """委託/成交回報"""
        ...

    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...
```

---

### 3. Risk Engine（風控引擎）

交易前、中、後的風險控管。

```
risk_engine/
├── pre_trade/           # 下單前檢查
│   ├── position_limit.py    # 部位上限
│   ├── order_limit.py       # 單筆委託金額/數量限制
│   ├── concentration.py     # 集中度檢查
│   └── blacklist.py         # 黑名單（禁止交易標的）
├── realtime/            # 即時監控
│   ├── drawdown.py      # 最大回撤監控（觸發停損）
│   ├── pnl_monitor.py   # 即時損益監控
│   ├── exposure.py      # 曝險度監控
│   └── circuit_breaker.py   # 熔斷機制（異常行為自動停機）
├── post_trade/          # 交易後分析
│   ├── attribution.py   # 績效歸因
│   └── compliance.py    # 合規檢查
└── config.py            # 風控參數設定
```

**風控規則範例：**

| 規則 | 說明 | 預設值 |
|------|------|--------|
| 單一標的持倉上限 | 佔總資金比例 | 10% |
| 日損失上限 | 當日虧損達此值停止交易 | -2% |
| 最大回撤停機 | 累計回撤達此值全部平倉 | -5% |
| 單筆委託上限 | 單筆金額上限 | 100 萬 |
| 每分鐘下單頻率 | 防止異常高頻 | 10 筆 |

---

### 4. Execution Engine（執行引擎）

實際與券商 API 互動，管理委託生命週期。

```
execution_engine/
├── broker/              # 券商介面
│   ├── base.py          # 抽象券商介面
│   ├── shioaji.py       # 永豐 Shioaji 實作
│   └── simulated.py     # 模擬券商（紙上交易 / 回測用）
├── order_manager.py     # 委託管理器（追蹤委託狀態）
├── position_manager.py  # 持倉管理器
├── smart_order/         # 智慧下單
│   ├── twap.py          # 時間加權均價
│   ├── vwap.py          # 成交量加權均價
│   └── iceberg.py       # 冰山單（大單拆小單）
└── reconciliation.py    # 對帳（本地紀錄 vs 券商紀錄）
```

**執行流程：**

```
Signal → Risk Check → Order Creation → Broker API → Order Tracking → Fill/Reject
  ↑                                                        │
  └────────────── Feedback Loop ───────────────────────────┘
```

---

### 5. Monitoring & Dashboard（監控與儀表板）

```
monitoring/
├── dashboard/           # Web 儀表板
│   ├── app.py           # FastAPI / Streamlit
│   ├── pages/
│   │   ├── overview.py      # 總覽（資金曲線、今日損益）
│   │   ├── positions.py     # 持倉明細
│   │   ├── orders.py        # 委託紀錄
│   │   └── strategy.py      # 策略績效
│   └── websocket.py     # 即時推送
├── alerts/              # 告警系統
│   ├── notifier.py      # 通知發送（LINE / Telegram / Discord）
│   ├── rules.py         # 告警規則
│   └── templates/       # 通知模板
└── logging/             # 日誌
    ├── trade_log.py     # 交易日誌
    └── system_log.py    # 系統日誌
```

---

### 6. Core Infrastructure（核心基礎設施）

```
core/
├── event_bus.py         # 事件匯流排（發布/訂閱模式）
├── scheduler.py         # 排程器（開盤前準備、收盤後結算）
├── config.py            # 全域設定管理
├── models/              # 資料模型
│   ├── market.py        # MarketData, OHLCV, Tick
│   ├── order.py         # Order, Fill, OrderStatus
│   ├── position.py      # Position, Portfolio
│   └── signal.py        # Signal, SignalType
└── utils/
    ├── time_utils.py    # 台股交易時間判斷
    ├── tw_calendar.py   # 台股交易日曆（休市日）
    └── decimal_utils.py # 精確小數運算（避免浮點誤差）
```

---

## 系統事件流

```
                    ┌──────────────┐
                    │  Market Open │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Data Engine │  ← 即時行情串流
                    │  (Tick/K線)  │
                    └──────┬───────┘
                           │ MarketDataEvent
                    ┌──────▼───────┐
                    │   Strategy   │  ← 策略運算
                    │    Engine    │
                    └──────┬───────┘
                           │ SignalEvent
                    ┌──────▼───────┐
                    │  Risk Engine │  ← 風控檢查
                    │  (Pre-trade) │
                    └──────┬───────┘
                           │ OrderEvent (approved)
                    ┌──────▼───────┐
                    │  Execution   │  ← 送出委託
                    │    Engine    │
                    └──────┬───────┘
                           │ FillEvent
                    ┌──────▼───────┐
                    │  Monitoring  │  ← 紀錄 & 通知
                    └──────────────┘
```

---

## 技術選型

| 層級 | 技術 | 原因 |
|------|------|------|
| 語言 | Python 3.12+ | Shioaji 官方支援、量化生態豐富 |
| 券商 API | Shioaji | 永豐金證券，台股完整支援 |
| 即時通訊 | ZeroMQ / asyncio | 低延遲事件傳遞 |
| 時序資料庫 | TimescaleDB (PostgreSQL) | 高效時序查詢、SQL 相容 |
| 快取 | Redis | 即時報價快取、跨模組共享狀態 |
| Web 框架 | FastAPI + WebSocket | 非同步、即時推送 |
| 儀表板 | Streamlit 或 React | 快速原型 / 正式版 |
| ML 框架 | scikit-learn / PyTorch | 訊號模型 |
| 排程 | APScheduler | 定時任務（開盤前、收盤後） |
| 通知 | LINE Notify / Discord Bot | 告警推送 |
| 容器化 | Docker + docker-compose | 部署一致性 |

---

## 目錄結構總覽

```
quant-system/
├── ARCHITECTURE.md          # 本文件
├── README.md
├── pyproject.toml           # 專案設定 & 依賴管理
├── docker-compose.yml
├── .env.example             # 環境變數範本（API Key 等）
│
├── core/                    # 核心基礎設施
├── data_engine/             # 資料引擎
├── strategy_engine/         # 策略引擎
├── risk_engine/             # 風控引擎
├── execution_engine/        # 執行引擎
├── monitoring/              # 監控與儀表板
│
├── configs/                 # 設定檔
│   ├── strategy/            # 各策略參數
│   ├── risk/                # 風控參數
│   └── broker/              # 券商連線設定
│
├── notebooks/               # 研究用 Jupyter Notebook
│   ├── research/            # 策略研究
│   └── analysis/            # 績效分析
│
├── tests/                   # 測試
│   ├── unit/
│   ├── integration/
│   └── backtest/            # 回測驗證
│
├── scripts/                 # 工具腳本
│   ├── download_data.py     # 下載歷史資料
│   ├── run_backtest.py      # 執行回測
│   └── deploy.py            # 部署腳本
│
└── logs/                    # 日誌輸出
```

---

## 開發路線建議

### Phase 1：基礎建設（2-3 週）
- [ ] Core 資料模型定義
- [ ] Shioaji 券商介面封裝
- [ ] 歷史資料下載與儲存
- [ ] 模擬券商（紙上交易）

### Phase 2：策略框架（2-3 週）
- [ ] 策略基底類別與事件系統
- [ ] 回測引擎
- [ ] 第一個簡單策略（如 MA 交叉）
- [ ] 回測績效報告

### Phase 3：即時交易（2-3 週）
- [ ] 即時行情串流接入
- [ ] 風控引擎（基本規則）
- [ ] 委託管理與成交追蹤
- [ ] 紙上交易驗證

### Phase 4：監控與優化（2 週）
- [ ] 儀表板（損益、持倉、委託）
- [ ] LINE / Discord 告警通知
- [ ] 參數優化工具
- [ ] 日誌與對帳

### Phase 5：進階功能（持續迭代）
- [ ] ML 訊號模型整合
- [ ] 多策略組合與資金分配
- [ ] 智慧下單演算法（TWAP/VWAP）
- [ ] 績效歸因分析

---

## 核心設計原則

1. **事件驅動**：所有模組透過事件匯流排通訊，低耦合、易測試
2. **策略與執行分離**：策略只產生訊號，不直接下單；便於回測與實盤切換
3. **風控前置**：每筆交易必經風控檢查，硬性規則不可繞過
4. **可回測性**：同一策略程式碼可無縫切換回測 / 紙上交易 / 實盤
5. **故障安全**：異常時自動停機（熔斷），寧可不交易也不亂交易
6. **可觀測性**：完整的日誌、指標、告警，隨時掌握系統狀態
