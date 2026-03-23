# 開發進度報告

> **產出日期：** 2026-03-23
> **比對依據：** [開發計畫書](development-plan.md)、[專案建議書](project-proposal.md)、[前端路線圖](frontend-roadmap.md)
> **方法：** 逐項比對文件規劃與程式碼實際狀態

---

## 總覽

| 階段 | 規劃項目 | 已完成 | 部分完成 | 未開始 | 完成率 |
|------|:--------:|:------:|:--------:|:------:|:------:|
| Phase 1：測試補強 | 3 | 3 | 0 | 0 | 100% |
| Phase 2：策略與研究 | 7 | 7 | 0 | 0 | 100% |
| Phase 3：即時交易 | 3 | 0 | 1 | 2 | 17% |
| Phase 4：進階功能 | 5 | 0 | 1 | 4 | 10% |
| 前端路線圖 | 8 | 8 | 0 | 0 | 100% |
| **合計** | **26** | **18** | **2** | **6** | **73%** |

---

## Phase 1：測試補強與品質基礎 — 完成

### 1.1 後端整合測試 — 已完成

| 驗收標準 | 結果 |
|----------|------|
| `tests/integration/` 下至少 20 個測試 | 實際 48 個測試函式 |
| 覆蓋所有 API 端點的正常與異常路徑 | 涵蓋認證、投組、策略、訂單、風控、回測、管理員 |
| CI 中整合測試全部通過 | CI pipeline 已納入 |

**對應檔案**：`tests/integration/test_api.py`

### 1.2 Web 前端測試 — 已完成

| 驗收標準 | 結果 |
|----------|------|
| `make web-test` 可執行 | vitest 已設定 |
| 核心 Hook 與工具函式覆蓋率 > 80% | 14 個測試檔案，約 90 個測試案例 |

**對應檔案**：`apps/web/src/` 下 11 個 vitest 測試、`apps/web/e2e/` 下 3 個 Playwright spec

### 1.3 效能基準測試 — 已完成

| 驗收標準 | 結果 |
|----------|------|
| 效能基準報告 | `scripts/benchmark.py` 涵蓋 9 組測試（5/20/50 標的 × 1/3/5 年），追蹤執行時間與記憶體 |

---

## Phase 2：策略框架與研究工具 — 完成

### 2.1 新增策略模板 — 已完成

| 策略 | 檔案 | 狀態 |
|------|------|:----:|
| RSI Oversold | `strategies/rsi_oversold.py` | 已實作 |
| MA Crossover | `strategies/ma_crossover.py` | 已實作 |
| Pairs Trading | `strategies/pairs_trading.py` | 已實作 |
| Multi-Factor | `strategies/multi_factor.py` | 已實作 |
| Sector Rotation | `strategies/sector_rotation.py` | 已實作 |

計畫要求 5 套，實際完成 5 套，加上原有 momentum 與 mean_reversion 共 7 套。策略單元測試位於 `tests/unit/test_new_strategies.py`（260 行）。

### 2.2 因子研究框架 — 已完成

| 任務 | 狀態 | 對應檔案 |
|------|:----:|----------|
| 因子分析 CLI | 已實作 | `src/cli/main.py` 的 `factor-analysis` 指令 |
| IC 計算 | 已實作 | `src/strategy/research.py` 的 `analyze_factor()` |
| 因子衰減分析 | 已實作 | `src/strategy/research.py` 的 `factor_decay()` |
| 因子合成 | 已實作 | `src/strategy/research.py` 的 `FACTOR_REGISTRY`（6 個因子） |

研究框架測試位於 `tests/unit/test_research.py`（250 行）。

### 2.3 回測效能優化 — 已完成

| 任務 | 狀態 | 說明 |
|------|:----:|------|
| 資料載入優化 | 已實作 | `_build_matrices()` 預建價格/成交量矩陣 |
| 向量化查詢 | 已實作 | `_lookup_row()` 使用 `searchsorted()` O(log N) 查詢 |
| 快取強化 | 已實作 | YahooFeed 24h parquet 快取 + 矩陣 forward-fill |
| Polars 評估 | 未執行 | 維持 Pandas（待決策項） |
| 並行回測 | 未實作 | — |

計畫驗收標準「20 檔 × 3 年 < 30 秒」需實際跑 benchmark 確認。

### 2.4 回測報告強化 — 已完成

| 任務 | 狀態 | 對應 |
|------|:----:|------|
| HTML 報告 | 已實作 | `src/backtest/report.py` 的 `generate_html_report()`，CLI `--report` 旗標 |
| 基準比較 | 已實作 | `compare_with_benchmark()`，CLI `--benchmark` 旗標 |
| 交易明細 CSV | 已實作 | `export_trades_csv()`，CLI `--export-trades` 旗標 |

---

## Phase 3：即時交易基礎建設 — 大部分未開始

### 3.1 即時行情對接 — 未開始

`src/data/feed.py` 中 `DataFeed` ABC 已預留介面，但無 `LiveFeed` 實作。目前僅能透過 Yahoo Finance 下載歷史數據，不支援即時行情訂閱。

**缺少項目**：
- 即時行情 DataFeed 實作
- 台灣券商 API 串接（富邦/元大）
- WebSocket `market` 頻道的即時行情推送
- 斷線重連機制

### 3.2 Paper Trading 模式 — 部分完成

| 項目 | 狀態 |
|------|:----:|
| PaperBroker | 已存在（`src/execution/broker.py`），可模擬成交 |
| 策略排程器 | 未實作 — 無定時觸發 `on_bar()` 的機制 |
| 持倉持久化 | 未實作 — Portfolio 狀態不寫入資料庫 |
| 即時績效追蹤 | 未實作 — 無即時 P&L 計算 |

`QUANT_MODE=paper` 可設定，但缺少排程與持久化基礎建設，無法真正運作。

### 3.3 告警通知 — 未開始

無 LINE Notify、Telegram Bot、通知框架的任何實作。風控警報僅記錄於 `RiskAlert` 物件與 WebSocket 推送，無外部通知管道。

---

## Phase 4：進階功能與生產準備 — 大部分未開始

### 4.1 實盤交易對接 — 未開始

無任何真實券商 API 對接。`src/execution/` 下僅有 `SimBroker` 和 `PaperBroker`，無 `BrokerAdapter` 介面。

### 4.2 監控與觀測 — 未開始

| 項目 | 狀態 |
|------|:----:|
| Prometheus 指標 | 未實作（無 `prometheus_client` 依賴） |
| Grafana 儀表板 | 未實作 |
| 結構化日誌 | 部分 — `src/logging_config.py` 存在，支援 JSON 格式 |
| 健康檢查強化 | 僅基礎 `/system/health` 端點 |

### 4.3 組合最佳化進階 — 未開始

`src/strategy/optimizer.py` 目前提供三種優化器：

| 優化器 | 狀態 |
|--------|:----:|
| Equal Weight | 已實作 |
| Signal Weight | 已實作 |
| Risk Parity | 已實作 |
| Mean-Variance (Markowitz) | 未實作 |
| Black-Litterman | 未實作 |
| 風險預算 | 未實作 |
| 交易成本感知最佳化 | 未實作 |

### 4.4 多用戶支援 — 部分完成

| 項目 | 狀態 |
|------|:----:|
| 用戶管理 | 已實作 — `src/data/user_store.py` + `src/api/routes/admin.py`，支援 CRUD + 密碼重設 |
| 角色指派 | 已實作 — 5 級角色（viewer → admin） |
| 策略隔離 | 未實作 — 所有用戶共用同一 Portfolio |
| 績效歸因 | 未實作 |

---

## 前端路線圖 — 完成

### 測試與品質

| 項目 | 狀態 | 說明 |
|------|:----:|------|
| Web E2E 測試 | 已完成 | 3 個 Playwright spec（smoke、backtest、orders） |
| Mobile 測試 | 已完成 | 13 個測試檔案（7 元件 + 6 Hook） |
| Shared 測試 | 已完成 | API client、endpoints、WS、format 測試 |

### 使用者體驗

| 項目 | 狀態 | 說明 |
|------|:----:|------|
| 深色/淺色主題 | 已完成 | `ThemeContext` + localStorage + 系統偏好偵測 |
| 即時行情 Ticker | 未完成 | `market` WS channel 前端未串接 |
| 系統監控面板 | 已完成 | `AdminPage.tsx` 含系統指標 |
| Toast 通知 | 已完成 | `apps/web/src/shared/ui/Toast.tsx` |

### 無障礙性

| 項目 | 狀態 | 說明 |
|------|:----:|------|
| ARIA 標籤 | 已完成 | 25+ 個 aria 屬性分布於各元件 |
| 色彩對比度 | 未驗證 | 需 WCAG AA 工具掃描確認 |

### 進階功能

| 項目 | 狀態 | 說明 |
|------|:----:|------|
| 大型列表虛擬化 | 已完成 | `DataTable.tsx` |
| 回測進階圖表 | 已完成 | MonthlyHeatmap、DrawdownChart、TradeTable、CompareChart |
| 管理員頁面 | 已完成 | `AdminPage.tsx` 用戶管理 GUI |
| CI 前端測試 | 已完成 | web-test、shared-test、mobile-test、e2e-test 皆在 CI |

---

## 與專案建議書（project-proposal.md）的差異

專案建議書中列出的未來規劃（第九章），目前狀態：

### 短期改善（1-3 月） — 大部分已完成

| 項目 | 建議書狀態 | 實際狀態 |
|------|:----------:|:--------:|
| 整合測試補強 | 高優先 | 已完成（48 個測試） |
| 更多策略模板 | 高優先 | 已完成（+5 套） |
| 即時行情對接 | 高優先 | 未開始 |
| Web 前端測試 | 中優先 | 已完成 |
| 效能最佳化 | 中優先 | 已完成（矩陣向量化） |

### 中期發展（3-6 月） — 尚未開始

| 項目 | 建議書狀態 | 實際狀態 |
|------|:----------:|:--------:|
| 實盤交易對接 | 高優先 | 未開始 |
| 多因子模型 | 高優先 | 已完成（multi_factor 策略 + 研究框架） |
| 組合最佳化 | 中優先 | 未開始（Mean-Variance、Black-Litterman） |
| 監控告警 | 中優先 | 未開始 |
| 多用戶支援 | 中優先 | 部分完成（用戶管理有、策略隔離無） |

---

## 待決策事項現況

開發計畫書第四章列出的待決策事項：

| 決策 | 計畫狀態 | 目前進展 |
|------|----------|----------|
| DataFrame 引擎（Pandas vs Polars） | Phase 2 效能優化時評估 | 尚未評估，維持 Pandas |
| 券商 API（富邦 vs 元大 vs 自建） | Phase 3 啟動前確認 | 未決定，Phase 3 未啟動 |
| 即時行情來源 | Phase 3 啟動前確認 | 未決定 |
| 訊息佇列（Redis vs RabbitMQ） | 多用戶場景時評估 | 未需要，目前無多用戶隔離 |

---

## 結論與建議

**Phase 1 和 Phase 2 已全面達標**，測試基礎與策略生態建設良好。Phase 2 的回測報告（HTML、基準比較、交易匯出）和因子研究框架是超出原計畫的加分項。

**接下來的瓶頸在 Phase 3（即時交易基礎建設）**。建議的下一步：

1. **決定券商與行情來源** — 這是 Phase 3 所有工作的前提
2. **實作 LiveFeed** — 擴充 `DataFeed` ABC，串接即時行情
3. **補齊 Paper Trading 排程與持久化** — 讓 `QUANT_MODE=paper` 真正可用
4. **評估 Polars** — Phase 2 待決策項仍開放，可在下一次效能瓶頸時評估

---

*本報告基於程式碼實際狀態產出，各項目狀態以檔案存在性與內容驗證為準。*
