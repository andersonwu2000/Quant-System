# 系統改善計畫 — 從原型到生產級的真實缺口

**日期**：2026-03-31
**背景**：外部評價指出 6 項「技術缺口」，經逐條比對代碼後，其中 5 項已實作完成（評價者未讀代碼）。本文聚焦**真正的缺口**。

---

## 0. 外部評價 vs 實際狀態

| 外部指出的缺口 | 實際狀態 | 結論 |
|---------------|---------|------|
| 缺乏事件驅動回測引擎 | `engine.py` 事件驅動 + `vectorized.py` 快速驗證，雙引擎並行 | ❌ 不成立 |
| 缺乏錯誤處理與狀態持久化 | `portfolio_state.json` + SQLite + trade logs + crash recovery | ❌ 不成立 |
| 風控層與策略耦合 | `src/risk/` 12 條獨立規則 + Kill Switch + RealtimeMonitor | ❌ 不成立 |
| 缺乏監控與警報 | Discord/LINE/Telegram webhook + structlog + Kill Switch 通知 | ❌ 不成立 |
| 缺乏 Docker 與環境管理 | docker-compose + `.env` + `QUANT_*` 環境變數 + CI 9 jobs | ❌ 不成立 |
| 缺乏滑價與手續費 | SimBroker: commission 0.1425% + sell tax 0.3% + spread slippage + volume impact | ❌ 不成立 |

**教訓**：表面評價不可靠。系統的真正弱點在更深的地方。

---

## 1. 真正的技術缺口（按優先級排序）

### G1. 實盤 vs 回測一致性驗證 — P0

**現狀**：Paper trading 3/21 啟動，已跑 10 天，但沒有系統性方法比對「回測預期」vs「實際表現」。

**風險**：回測看起來好的策略可能因為以下原因在實盤表現不同：
- 成交價假設不同（回測用 close，實盤用 SimBroker 撮合價）
- 再平衡時機差異（回測 bar-end rebalance，實盤 09:03 下單）
- 數據差異（回測用歷史 parquet，實盤用即時 yfinance）

**改善方案**：

```
┌─────────────────────────────────────────────────────┐
│  Paper Trading Reconciliation Pipeline              │
│                                                     │
│  每日 13:30 EOD 時：                                │
│  1. 讀取當日 paper trades（SimBroker 成交記錄）     │
│  2. 用相同日期的歷史數據跑一次回測                  │
│  3. 比對：target_weights vs actual_weights          │
│          expected_return vs actual_return            │
│          expected_cost vs actual_cost                │
│  4. 差異 > 閾值 → Discord 告警                     │
│  5. 累積到 weekly report                           │
└─────────────────────────────────────────────────────┘
```

**具體步驟**：

| 步驟 | 內容 | 檔案 |
|------|------|------|
| G1.1 | Reconciliation 數據結構（expected vs actual） | `src/reconciliation/models.py` |
| G1.2 | 每日 EOD reconciliation job | `src/reconciliation/daily.py` |
| G1.3 | Implementation shortfall 分析（已有基礎） | 擴展 `src/execution/analytics.py` |
| G1.4 | Weekly reconciliation report | `src/reconciliation/report.py` |
| G1.5 | 排程整合（13:30 EOD） | 修改 `src/scheduler/jobs.py` |

**成功標準**：連續 30 個交易日，回測 vs 實盤的 daily return 差異 < 50bps。

---

### G2. Survivorship Bias 整合 — P0

**現狀**：`SecuritiesMaster` 已建好，`universe_at(date)` PIT 查詢已實作，但回測引擎還沒用它。

**風險**：回測用當前 universe（只含現在上市的股票），錯過了已下市的股票。研究顯示 survivorship bias 可膨脹年化報酬 1-2%。

**改善方案**：

| 步驟 | 內容 | 檔案 |
|------|------|------|
| G2.1 | 回填 SecuritiesMaster 歷史數據（上市/下市日） | `src/data/master.py` + TWSE 爬蟲 |
| G2.2 | 回測引擎 `_load_data` 用 `universe_at(date)` | 修改 `src/backtest/engine.py` |
| G2.3 | 每月自動同步上市/下市清單 | `src/scheduler/jobs.py` |
| G2.4 | 驗證：比較 PIT universe vs 現有 universe 的回測差異 | 實驗報告 |

**成功標準**：回測引擎預設使用 PIT universe，手動 opt-out。

---

### G3. 多資產組合最佳化串接 — P1

**現狀**：
- `src/portfolio/` 有 14 種最佳化方法（MVO, Black-Litterman, Risk Parity...）
- `src/allocation/` 有宏觀因子 + 跨資產信號
- 但這些只在回測中用，**paper trading pipeline 只跑單一策略**

**風險**：無法實現「股票 alpha + 債券 ETF 防守 + 期貨對沖」的完整組合。

**改善方案**：

| 步驟 | 內容 | 檔案 |
|------|------|------|
| G3.1 | Multi-strategy pipeline（多策略同時跑，合併 weights） | `src/scheduler/multi_strategy.py` |
| G3.2 | Portfolio optimizer 整合進 pipeline | 修改 `src/scheduler/jobs.py` |
| G3.3 | Cross-asset rebalancing（股+ETF 聯合再平衡） | `src/portfolio/cross_asset.py` |
| G3.4 | Paper trading 支援多帳戶/多策略 | 擴展 portfolio state |

**成功標準**：paper trading 能同時跑 2+ 策略，用 optimizer 合併後下單。

---

### G4. 掛單狀態追蹤與恢復 — P1

**現狀**：
- Portfolio state（持倉、現金、NAV）已持久化 ✅
- Trade log 已持久化 ✅
- **但掛單（pending orders）沒有持久化**

**風險**：程式在下單後、成交前崩潰，重啟後不知道有未成交單。台股日頻月再平衡影響小（再平衡日才下單），但頻率提高後風險上升。

**改善方案**：

| 步驟 | 內容 | 檔案 |
|------|------|------|
| G4.1 | OrderBook 持久化（pending orders → SQLite） | `src/execution/order_book.py` |
| G4.2 | 重啟時載入未成交單 | 修改 `src/execution/service.py` |
| G4.3 | Reconcile：對帳未成交單 vs 交易所狀態 | 需要 Sinopac API 整合 |
| G4.4 | 超時未成交單自動取消 + 告警 | 修改 `src/risk/` |

**成功標準**：模擬崩潰重啟後，系統能正確處理所有 pending orders。

---

### G5. Tick-level 撮合（低優先）— P2

**現狀**：回測引擎是 bar-level（日 K），SimBroker 在 bar 內用 OHLCV 模擬成交（open/close/high/low 做價格邊界檢查）。

**真正需求**：只有在以下場景需要 tick-level：
- 日內策略（5m/1m bar）
- 高頻做市
- 精確模擬 limit order fill probability

**台股日頻月再平衡**不需要 tick-level 撮合。現有 bar-level + slippage model 已足夠。

**改善方案（需要時再做）**：

| 步驟 | 內容 |
|------|------|
| G5.1 | Tick data 取得管道（Sinopac real-time → parquet） |
| G5.2 | SimBroker 支援 tick-by-tick 撮合模式 |
| G5.3 | Limit order fill probability model |

---

## 2. 執行順序

```
Phase 1（本週-下週）：
  G1.1-G1.3  Reconciliation 基礎（paper trading 已在跑，越早開始比對越好）
  G2.1-G2.2  Survivorship bias（SecuritiesMaster 已就緒，差回測引擎整合）

Phase 2（兩週內）：
  G1.4-G1.5  Weekly report + 排程
  G2.3-G2.4  自動同步 + 驗證實驗
  G3.1-G3.2  Multi-strategy pipeline

Phase 3（一個月內）：
  G3.3-G3.4  Cross-asset rebalancing
  G4.1-G4.4  掛單狀態追蹤

Phase 4（需要時）：
  G5          Tick-level 撮合
```

---

## 3. 已完成的基礎設施（不需重做）

以下是外部評價認為缺少、但實際已完成的組件：

| 組件 | 實作位置 | 測試覆蓋 |
|------|---------|---------|
| 事件驅動回測引擎 | `src/backtest/engine.py` | 200+ tests |
| SimBroker（滑價+手續費+T+2） | `src/execution/broker/simulated.py` | 50+ tests |
| 風控引擎（12 規則） | `src/risk/` | 80+ tests |
| Kill Switch | `src/risk/kill_switch.py` | 有 |
| Discord/LINE/Telegram 通知 | `src/notifications/` | 有 |
| Portfolio 持久化 | `portfolio_state.json` + SQLite | 有 |
| Docker 部署 | `docker-compose.yml` × 2 | CI 整合 |
| 環境變數管理 | `src/core/config.py` (`QUANT_*`) | 有 |
| structlog 日誌 | 全系統 | — |
| 數據平台（Phase AD） | `src/data/` 8 個新模組 | 33 tests |
| 1,700+ 單元測試 | `tests/unit/` | CI 自動跑 |

---

## 4. 度量指標

| 指標 | 目標 | 當前 |
|------|------|------|
| 回測 vs 實盤 daily return 差異 | < 50bps | 無數據（G1 未做） |
| Survivorship bias 修正後 CAGR 差異 | 量化 | 無數據（G2 未做） |
| 多策略 paper trading | 2+ 策略同時跑 | 1 策略 |
| 掛單恢復成功率 | 100% | 0%（未實作） |
| 測試覆蓋率 | 1,800+ tests | 1,700+ tests |
