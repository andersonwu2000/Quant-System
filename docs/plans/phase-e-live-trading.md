# Phase E：實盤交易

> 完成日期：2026-03-25
> 狀態：✅ 程式碼完成，模擬整合通過 (2026-03-26)，待 CA 憑證進行生產測試

## 目標
建立從策略到實際券商下單的完整交易管道。

## 券商選擇
永豐金 Shioaji SDK — 評估見 `docs/dev/evaluations/BROKER_API_EVALUATION.md`
- Python 原生、跨平台、`simulation=True` 一鍵切換
- 認證：api_key + secret_key → CA 憑證 (.pfx)

## 產出
- **SinopacBroker** (`src/execution/sinopac_broker.py`): Shioaji SDK 封裝 — 非阻塞下單(timeout=0)、OrderState callback、斷線重連、trading_limits/settlements/dispositions 查詢
- **ExecutionService** (`src/execution/execution_service.py`): 模式路由 backtest→SimBroker / paper→SinopacBroker(sim=True) / live→SinopacBroker
- **SinopacQuoteManager** (`src/execution/sinopac_quote.py`): tick/bidask STK+FOP callback → TickData/BidAskData
- **ShioajiFeed** (`src/data/sources/shioaji_feed.py`): 1 分鐘 K 棒 + tick + snapshot（2020-03 起）
- **ShioajiScanner** (`src/data/scanner.py`): 成交量/漲跌排行 + 處置/注意股排除 + 動態 universe
- **StopOrderManager** (`src/execution/stop_order.py`): 軟體觸價委託
- **Market Hours** (`src/execution/market_hours.py`): 台股時段驗證 + 盤外佇列
- **EOD Reconcile** (`src/execution/reconcile.py`): 持倉對帳 + auto_correct
- **Order 擴展**: OrderCondition (Cash/Margin/Short/DayTrade) + StockOrderLot (Common/IntradayOdd/Odd/Fixing)
- **Scheduler**: `execute_rebalance()` 接通策略→風控→下單→Portfolio→通知

## Shioaji 整合測試結果 (2026-03-26)

**API Key 已取得，模擬模式 (simulation=True) 驗證通過。**

### 模擬環境通過項目
- Shioaji login (simulation=True) — 連線成功
- 基本下單流程 — submit_order / cancel_order
- 帳務查詢 — query_trading_limits / query_settlements
- 處置股查詢 — check_dispositions

### 需生產環境 CA 憑證
- Deal callback（成交回報）— 模擬環境無真實撮合回報
- Tick/BidAsk streaming — 需 CA 憑證才能訂閱即時行情
- Paper Trading 完整循環 — 排程→下單→回報→對帳→通知
- WS `market` 頻道接入即時行情
