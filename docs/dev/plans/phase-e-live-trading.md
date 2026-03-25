# Phase E：實盤交易

> 完成日期：2026-03-25
> 狀態：✅ 程式碼完成，待 API Key 整合測試

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

## 待 API Key 後
- 整合測試（真實 Shioaji login/下單/行情）
- Paper Trading 完整循環驗證
- WS `market` 頻道接入即時行情
