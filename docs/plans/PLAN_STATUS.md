# Phase Plan Status — 總覽表

> Last updated: 2026-04-01 (session 5 — 全面代碼審計，AA~AK 逐項驗證)
> Total: 35 phases | Done: 24 | In Progress: 4 | Paused: 2 | Not Started: 1 | Superseded: 4

---

## 已完成（24）

| Phase | 名稱 | 備註 |
|:-----:|------|------|
| A | 多資產基礎設施 | Instrument Registry, FX, FRED |
| B | 跨資產 Alpha | MacroFactorModel, TacticalEngine |
| C | 投組優化 | 6 種方法（MVO, Black-Litterman, Risk Parity...） |
| D | 系統整合 | 跨資產風控 |
| F | 自動 Alpha 研究 | AutoAlpha 12 files |
| G | 學術升級 | CVaR, robust optimization, 13 portfolio methods |
| H | 實務改進 | Deflated Sharpe, Semi-variance, Kalman |
| I | 因子庫擴展 | 27 factors (Kakushadze + Fama-French) |
| K | 數據品質 | 基本面因子驗證 |
| L | 策略轉向 | 營收動量 + 法人跟隨 + 篩選管線 |
| M | 下檔保護 | Regime-aware position sizing |
| R | 代碼整潔 | Phase tracker, .env 文檔 |
| S | Pipeline 統一 | 3 條管線合併為 1 |
| U | Autoresearch 模式 | Karpathy 3-file 架構 |
| V | Kill Switch Debug | 核心 3 bug 已修，路徑鎖定 |
| X | 反過擬合 | L5 gate + 複雜度限制 |
| Y | 容器化研究 | Docker 3-container 隔離 |
| Z | 向量化回測 | PBO + SharedFeed (Z1+Z2 done, Z3 deferred) |
| AB | Factor-Level PBO | daily returns 儲存 + CSCV + hierarchical clustering + DSR(N=15) |
| AC | Validator 方法論修正 | 16 項檢查 + §7 hard/soft 門檻分離 |
| AD | 數據管線自動化 | DataCatalog + Registry + SecuritiesMaster + QualityGate + RefreshEngine |
| AE | Docker Agent 隔離 | 3-container + loop.ps1 + token refresh |
| AF | 記憶與替換系統 | learnings.jsonl + 1.3× 替換 + 飽和追蹤 + 深度限制 |
| AI | 營運架構 | daily_ops/eod_ops + Heartbeat + Trade Ledger + P0-P3 通知 |

## 進行中（4）

| Phase | 名稱 | 完成度 | 已做 | 未做 |
|:-----:|------|:------:|------|------|
| AA | 策略建構重構 | 80% | 4.2+4.6 no-trade zone + 非對稱成本（revenue_momentum.py）、sells-first、MODIFY cap、sqrt impact、odd-lot | Phase 2: strategy_builder 整合 construction.py（turnover penalty 代碼存在但未串接） |
| AG | 因子部署管線 | 75% | strategy_builder、paper_deployer、deployed_executor、refinement 2.5a+2.5c | Step 1 watchdog auto-submit（_auto_submit_factor 不存在）、Step 2.5b+2.5d（composite + stress） |
| AK | 整合測試體系 | 85% | 125 integration + 1 E2E + 2 security + 1 resilience | AK-4 效能基準（降為上線後）、E2E 缺 paper→live + autoresearch cycle |
| AJ | 壓力測試 | 50% | 框架 + 3 歷史情景 + 4 synthetic + 成本敏感度 | 缺 3 歷史情景（台股特有）、相關性壓力、因子失效測試 |
| **AL** | **Trading Safety** | **90%** | AL-1~10 實作完成：15 invariant + heartbeat + bare-except + 煙霧測試 + 一致性 + watchdog + 畢業檢查 | 等 30 天 paper 數據累積後驗證 G1/G4 |

## 暫停（2）

| Phase | 名稱 | 暫停原因 |
|:-----:|------|---------|
| E/N | 實盤交易 + Paper Trading | 等永豐金 CA 憑證 |
| AH | Web 前端改版 | 5/8 頁面完成（缺 Trading/Research/Orders），非阻塞項 |

## 未開始（1）

| Phase | 名稱 | 前置條件 |
|:-----:|------|---------|
| J | 跨資產 Alpha 擴展 | 台股因子研究穩定後 |

## 已取代 / 歸檔（4）

| Phase | 名稱 | 取代者 |
|:-----:|------|--------|
| P | 自動 Alpha 研究（舊版） | → Phase U |
| Q | 策略改進 | → Phase AA + AC |
| N2 | Web 前端重寫 | → Phase AH |
| M (v1) | 因子管理（舊版） | → Phase AD + AF |

---

## Live 前必完成項目

| 項目 | Phase | 狀態 |
|------|:-----:|:----:|
| 整合測試 125 tests | AK | ✅ |
| E2E test_full_trading_day | AK | ✅ |
| Auth 5 + 沙箱 14 security tests | AK | ✅ |
| Broker 斷線韌性 tests | AK | ✅ |
| Sinopac CA 憑證 | E | ⏳ 等待 |
| Paper mode 30 天觀察 | AG | ⏳ 未開始 |
| NAV 追蹤 < 1% 誤差 | AG | ⏳ 需驗證 |

---

## 研究進度

| 指標 | 數值 |
|------|------|
| 總實驗數 | 400+ |
| L5 通過（手動） | 2 (revenue_acceleration, per_value) |
| L5 通過（autoresearch） | 0 |
| 雙因子組合 | composite_growth_value (IS ICIR 0.364, OOS ICIR 0.571) |
| Validator 16 項 | hard/soft 分離完成，待重跑驗證 |
