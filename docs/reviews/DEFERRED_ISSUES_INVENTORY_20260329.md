# 擱置問題與可接受風險清查

**日期**：2026-03-29
**範圍**：docs/plans/ 全部 32 份計畫文件
**方法**：逐檔掃描所有標記為 deferred/postponed/acceptable risk/partial disagreement/monitor 的項目

---

## 統計摘要

| 類別 | 數量 | 佔比 |
|------|:----:|:----:|
| 延後到未來 Phase | 18 | 38% |
| 可接受風險 / 觀察 | 10 | 21% |
| 審批分歧（部分同意/不同意） | 6 | 13% |
| 已知缺漏未修 | 8 | 17% |
| 外部依賴等待中 | 2 | 4% |
| 未完成 / 進行中 | 3 | 6% |
| **合計** | **47** | |

---

## 1. 阻塞性項目（Critical Path）

這些項目阻塞了其他重要工作：

| # | 項目 | 來源 | 阻塞什麼 | 狀態 |
|---|------|------|---------|------|
| **CP-1** | CA 憑證未取得 | Phase N §N5 | 實盤交易 | 外部依賴（永豐金） |
| **CP-2** | Paper Trading 30 天驗證 | Phase R §R7 | 策略驗證、Phase S/T2 | 需等開盤 |
| **CP-3** | 生產級數據管線 | Phase AD（全部） | Paper Trading 上線 | 未開始 |
| **CP-4** | Factor-Level PBO 完整實作 | Phase AB Phase 2 | Phase X、AF 進階 | Phase 1 完成，Phase 2 待啟動 |

**CP-1 和 CP-2 是外部依賴**（券商、開盤），無法加速。**CP-3 和 CP-4 是內部工作**，可安排。

---

## 2. 方法論風險（已知但接受的）

這些是審計中識別的方法論問題，判斷為「可接受」但未修復：

### 2.1 OOS Sharpe 和 Recent Sharpe 統計功效不足

**來源**：Phase AC §3.4、FACTOR_PIPELINE_DEEP_REVIEW §2
**問題**：OOS Sharpe 的 SE = 0.82，Recent Sharpe 的 SE = 1.0。任何門檻都沒有檢定力（p > 0.30）。36-50% 的真實 SR=0 策略會通過。
**為何接受**：樣本量不足，不可修正（除非有 10+ 年未來數據）。已降級為 soft check（警告但不阻擋）。
**風險等級**：MEDIUM — 如果只靠這兩項做決策會出事，但系統有其他 6 個獨立維度的 check。
**建議**：維持現狀。Paper trading 是唯一有效的替代驗證。

### 2.2 Holdout 已被 233 次 adaptive query 降解

**來源**：FACTOR_PIPELINE_DEEP_REVIEW §1、Phase AF §7 問題 A
**問題**：Dwork budget ~4 次，實際用了 233 次（62×）。Russo & Zou bound: overfitting bias ≤ 17.5% 年化。
**為何接受**：不可逆。Thresholdout（Laplace noise）減緩但不消除。當前週期 L5 查詢 ~30 次，在 Thresholdout budget 內。
**風險等級**：HIGH — 舊週期的 holdout 已失效。新週期尚在安全範圍。
**建議**：嚴格追蹤 L5 query count。Phase AF 的替換機制設 10 次/週期上限（已在 AF §8 確認）。2026 Q2 結束後用全新的 OOS 期間。

### 2.3 E[max SR] from noise > 觀測 SR

**來源**：FACTOR_PIPELINE_DEEP_REVIEW §1
**問題**：N=15 獨立方向的噪音期望 Sharpe ≈ 1.4，我們觀測的最佳策略 Sharpe = 0.94。觀測值低於噪音期望。
**為何接受**：無法修正（是歷史實驗的事實）。但 Sharpe 0.94 不是唯一指標 — Permutation test、PBO、Bootstrap 從不同維度提供了額外證據。
**風險等級**：HIGH — 單看 Sharpe 無法排除「全是噪音」的可能。
**建議**：不依賴 Sharpe 做部署決策。Paper trading 是最終判斷。

### 2.4 所有 check 共用同一段歷史數據

**來源**：FACTOR_PIPELINE_DEEP_REVIEW §3
**問題**：16 項 Validator check 全部基於 2017-2024 台股數據。即使全部通過，也只代表在這特定 7 年行情中有效。
**為何接受**：不可修正（只有一個市場、一段歷史）。跨市場驗證缺失（無 US/Japan/Korea 數據）。
**風險等級**：MEDIUM — 結構性限制，非 bug。
**建議**：長期可加日股/韓股驗證。短期靠 paper trading + fresh holdout。

---

## 3. 審批分歧（Partial Disagreements）

這些是審查中出現的分歧，以折衷方案結案但雙方都有保留：

### 3.1 替換後 baseline_ic_series 是否保留 historical

**來源**：Phase AF §5 問題 3 vs §6 回覆
**審批意見**：保留 historical，防止被替換因子的「近親」復活
**作者反駁**：過度保守 — 近親復活可能是合法的（和新因子不相關）
**最終決議**：只用 active 做 dedup，Factor-Level PBO 捕捉整體風險。如果復活的因子都是 clone → 再加回 historical
**風險**：MEDIUM — 如果反駁錯了，clone 因子會復活膨脹因子庫

### 3.2 替換候選是否跑 L5

**來源**：Phase AF §7 問題 A vs §8 回覆
**審批意見**：不跑 L5，避免消耗 holdout
**作者反駁**：當前週期 L5 ~30 次在 budget 內；不跑 L5 的風險更大（IS-overfit 替換 OOS-stable）
**最終決議**：跑 L5 但設上限 10 次/週期
**風險**：LOW（折衷合理）— 但需追蹤 replacement_count

### 3.3 diversity_ratio 門檻

**來源**：Phase AF §7 問題 C vs §8 回覆
**審批意見**：先警告不阻擋
**作者反駁**：「只警告不阻擋 = 沒牙齒」
**最終決議**：雙門檻 — 0.30 WARN，0.15 BLOCK
**風險**：LOW — 0.30 和 0.15 都缺乏精確校準依據

### 3.4 記憶引導 vs multiple testing

**來源**：Phase AF §7 問題 B vs §8 回覆
**審批意見**：3x 效率可能是 3x overfitting
**作者反駁**：效率主要來自避免死路（forbidden zones），不是集中好方向；且 PBO 已用獨立假說聚類修正 N
**最終決議**：learnings 強調 forbidden zones，success patterns 附帶 saturation 標記
**風險**：MEDIUM — 如果 PBO 的聚類不準確，multiple testing 修正不足

### 3.5 AB Phase 3（獨立假說聚類）的 greedy clustering

**來源**：Phase AB §審批
**問題**：watchdog.py 的聚類用 greedy（column-order dependent），不是 hierarchical
**為何接受**：greedy 偏保守（可能高估 N），短期可接受
**最終決議**：延後到 Phase AB Phase 3 改用 hierarchical
**風險**：LOW — 保守方向的偏差（高估 N → DSR 偏嚴格）

### 3.6 1.3× 替換門檻用 ICIR 而非 IC

**來源**：Phase AF §5 問題 1 備註
**問題**：FactorMiner 的 1.3× 是對 IC，我們對 ICIR（更嚴格）。1.3× 這個數字沒有 ICIR 的校準依據
**最終決議**：作為起點可接受，後續用數據校準
**風險**：LOW — ICIR 更嚴格 = 保守方向

---

## 4. 延後的功能（Non-blocking）

| # | 項目 | 來源 | 延後原因 | 嚴重度 |
|---|------|------|---------|:------:|
| D-1 | Cross-asset ETF 擴展 | Phase J | 台股因子研究未穩定 | LOW |
| D-2 | Pipeline 三路徑統一 | Phase S | Phase R 阻塞 | MEDIUM |
| D-3 | 向量化回測引擎 Z3 | Phase Z | 現有效能可接受 | LOW |
| D-4 | Event-timing 再平衡 | Phase M L+.3 | 月度再平衡已足夠 | LOW |
| D-5 | 集保數據 + 市值數據 | Phase L §L1.5-L1.6 | 用 close×volume proxy | MEDIUM |
| D-6 | 前端 i18n + 測試 | Phase N2 Step 5 | 功能性完成 | LOW |
| D-7 | CPCV 交叉驗證 | Phase AC | PBO + DSR 已覆蓋 | LOW |
| D-8 | Regime 從年度改為 drawdown | Phase AC §3.4 | 年度夠用 | LOW |
| D-9 | Top-n 15→25 擴展 | Phase AA §4.3 | inverse-vol 失敗，先穩定 | MEDIUM |
| D-10 | construction.py 整合 | Phase AA §4.4-4.5 | 需改 on_bar 介面 | MEDIUM |
| D-11 | Lot size awareness | Phase AA §4.7 | Phase AB 已處理 | LOW |
| D-12 | Signal-driven rebalance | Phase AA §4.8 | 依賴 no-trade zone | LOW |

---

## 5. 已廢棄的計畫

| Phase | 被什麼取代 | 原因 |
|-------|----------|------|
| Phase P（Auto-Alpha Research） | Phase U（Karpathy 3-file） | 1800 行狀態機不可維護 |
| Phase Q（Strategy Refinement） | Phase AA + AC | 目標被拆分到兩個更聚焦的 Phase |
| Phase M 原版（Factor Management） | Phase AB | dedup 邏輯被 Factor-Level PBO 取代 |

---

## 6. Code Review 中發現但未修的 bug

這些是 CODE_REVIEW_20260329 中的項目，確認存在但尚未修復：

| # | Bug | 來源 | 嚴重度 | 狀態（代碼驗證 2026-03-29） |
|---|-----|------|:------:|------|
| B-1~B-3 | sinopac 零股 3 bug | C-01~C-03 | CRITICAL | ✅ 已修 — sinopac.py 有 `submitted_shares`, `lot_size`, `C-01`/`C-02`/`C-03` 標記 |
| B-4 | risk_parity 傳空 volatilities | C-07 | CRITICAL | ✅ 已修 — revenue_momentum.py:274 已計算 vols（`B-4 fix` 標記） |
| B-5 | apply_trades mutate Trade | H-04 | HIGH | ✅ 已修 — oms.py 用 `effective_qty`（`H-04` 標記） |
| B-6 | Context.get_revenue 無 fallback | C-06 | CRITICAL | ✅ 已修 — base.py:123 有 `.TW` fallback（`C-06` 標記） |
| B-7 | Kill switch path A 不 double-check | H-02 | HIGH | ✅ 已修（圖片確認：剛修） |
| B-8 | generate_liquidation_orders lock 外讀 | H-03 | HIGH | ✅ 已修（圖片確認：同 B-7） |
| B-9 | 手動 kill switch 不設 flag | M-06 | MEDIUM | ✅ 已修 |
| B-10 | sinopac callback lock 外寫 | M-01 | MEDIUM | ✅ 已修（圖片確認：剛修） |
| B-11 | auto_alpha name sanitization | M-02 | MEDIUM | ✅ 已修 — strip leading digits + `.isidentifier()` check |
| B-12 | auto_alpha importlib 繞過安全檢查 | M-03 | MEDIUM | ✅ 已修 — FORBIDDEN_PATTERNS 加入 `importlib`, `open(`, `sys`, `socket` 等 |
| B-13 | service.py sinopac_simulation 屬性 | M-05 | MEDIUM | ✅ 已修（圖片確認：已存在） |
| B-3c | execute_rebalance 無法平倉 | C-08/C-09 | CRITICAL | ✅ 已修 — jobs.py:193 和 360 都有 `_all_syms = set(target_weights) \| set(positions)` |

### 驗證修正（2026-03-29 最終確認）

初次 grep 被 `target_weights` 關鍵字誤導，實際 line 193 和 360 已有 `_all_syms` 修復。三條管線（execute_pipeline:664, execute_rebalance:193, monthly_revenue_rebalance:360）全部一致。

---

## 7. Phase AE Code Review 發現的問題

| # | Bug | 嚴重度 | 狀態 |
|---|-----|:------:|------|
| AE-H1 | evaluator 缺 strategies/ mount | HIGH | ✅ 已修 |
| AE-H2 | evaluator work/ 應為 ro | HIGH | ✅ 已修 |
| AE-M1 | factor.py race condition | MEDIUM | ❌ 延後（低機率） |
| AE-M2 | agent 容器缺 pandas（fallback 已移除） | MEDIUM | ✅ 已修（移除 fallback） |
| AE-M3 | eval_server 和 evaluate.py 格式耦合 | MEDIUM | ❌ 延後（fail-closed 安全） |

---

## 8. 優先級建議

### 立即修復（開盤前）

| 項目 | 原因 |
|------|------|
| B-1~B-6 重新修復 + regression test | 實盤交易路徑 CRITICAL bug，被 revert |
| AE-H1 strategies/ mount | evaluator 可能啟動失敗 |
| AE-H2 work/ 改 ro | 最小權限原則 |

### 開盤後優先

| 項目 | 原因 |
|------|------|
| CP-3 Phase AD（數據管線） | Paper trading 前置條件 |
| CP-2 Paper Trading 30 天 | 唯一有效的策略驗證 |

### 長期追蹤

| 項目 | 原因 |
|------|------|
| 2.2 Holdout 降解 | 追蹤 L5 query count，2026 Q2 換 fresh holdout |
| 2.3 SR < 噪音期望 | Paper trading 結果是最終判斷 |
| 3.1~3.4 審批分歧 | 觀察實際數據後再定論 |

---

## 9. 追蹤機制

建議每月覆核一次本文件：
- 已修復的項目標記 ✅ + 日期
- 新發現的問題追加
- 審批分歧項的後續觀察結果
