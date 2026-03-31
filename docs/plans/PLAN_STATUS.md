# Phase Plan Status — 總覽表

> Last updated: 2026-04-01 (session 2)
> Total: 35 phases | Done: 16 | In Progress: 10 | Not Started: 2 | Superseded: 4 | Archived: 3

---

## 已完成（16）

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
| S | Pipeline 統一 | 3 條管線合併為 1 |
| U | Autoresearch 模式 | Karpathy 3-file 架構 |
| Y | 容器化研究 | Docker 隔離 (agent+evaluator+watchdog) |
| Z | 向量化回測 | PBO + SharedFeed (Z1+Z2 done, Z3 deferred) |
| R | 代碼整潔 | Phase tracker, .env 文檔 |

## 進行中（10）

| Phase | 名稱 | 完成度 | 未完成項目 |
|:-----:|------|:------:|-----------|
| AA | 策略建構重構 | 60% | 4.1 inverse-vol 回滾（PBO 惡化），Phase 2 construction.py 整合 |
| AB | Factor-Level PBO | 75% | Step 4 auto-dedup 未做 |
| AC | Validator 方法論修正 | 85% | Hard/soft 門檻部署測試 |
| AD | 數據管線自動化 | 80% | Phase 4: TWSE 歷史端點、Securities Master、cross-source 驗證 |
| AE | Docker Agent 隔離 | 90% | Token refresh 已修（rw mount） |
| AG | 因子部署管線 | 65% | **Step 2.5 精煉管線未實作**（correlation check → 多因子組合 → Validator(no kill) → 壓力測試） |
| AH | Web 前端改版 | 70% | Trading page 核心功能 |
| AI | 營運架構 | 80% | Phase 5 (UI) optional |
| AK | 整合測試體系 | 85% | AK-4 效能基準（降為上線後） |
| AF | 記憶與替換系統 | 80% | 替換鏈深度限制已實作，飽和度追蹤已實作 |

## 部分完成但暫停（5）

| Phase | 名稱 | 完成度 | 暫停原因 |
|:-----:|------|:------:|---------|
| E | 實盤交易 | 90% | 等待永豐金 CA 憑證 |
| N | Paper Trading 準備 | 80% | N5 等 CA 憑證 |
| T | Paper Trading 完整性 | 60% | T2 回測比較部分完成，T3 自動對帳已修（live mode only） |
| V | Kill Switch Debug | 90% | 核心 3 bug 已修，路徑鎖定已做 |
| X | 反過擬合 | 80% | L5 gate 已實作，family labeling optional |

## 未開始（2）

| Phase | 名稱 | 前置條件 |
|:-----:|------|---------|
| AJ | 壓力測試 | 回測基礎設施穩定後 |
| J | 跨資產 Alpha 擴展 | 台股因子研究穩定後 |

## 已取代 / 歸檔（4）

| Phase | 名稱 | 取代者 |
|:-----:|------|--------|
| P | 自動 Alpha 研究（舊版） | → Phase U (autoresearch) |
| Q | 策略改進 | → Phase AA + AC |
| N2 | Web 前端重寫 | → Phase AH |
| M (v1) | 因子管理（舊版） | → Phase AD + AF |

---

## Live 前必完成項目

| 項目 | Phase | 狀態 |
|------|:-----:|:----:|
| AK-2 整合測試 59 tests（含 8 bug regression） | AK | ✅ |
| AK-3 E2E 4 tests | AK | ✅ |
| AK-5.1 Auth 5 tests + AK-5.2 沙箱 14 tests | AK | ✅ |
| AK-6 Broker 斷線韌性 3 tests | AK | ✅ |
| Sinopac CA 憑證 | E | ⏳ 等待 |
| Paper mode 30 天觀察 | AG | ⏳ 未開始 |
| 觀察期 0 假警報 | T | ✅ 已修（live mode only） |
| NAV 追蹤 < 1% 誤差 | AG | ⏳ 需驗證 |
| Reconciliation CLEAN | T | ✅ symbol 格式已修 |

---

## 研究進度

| 指標 | 數值 |
|------|------|
| 總實驗數 | 245+ |
| L5 通過（手動） | 2 (revenue_acceleration, per_value) |
| L5 通過（autoresearch） | 0 |
| 雙因子組合 | composite_growth_value (IS ICIR 0.364, OOS ICIR 0.571) |
| Validator 15 項 | 重跑中（kill switch OFF），首次 11/16 PASS（kill switch 觸發 20+ 次壓低 CAGR） |
