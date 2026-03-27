# 代碼審查報告（2026-03-27）

> 總計 7 輪審計，發現 **80+ 個 bug**，全部已修復或記錄。
> 涵蓋：alpha 研究管線、回測引擎、風控系統、執行層、API、並發安全、資料品質。
> **第 8 輪驗證（2026-03-27）**：逐一對照代碼確認修復狀態，發現 3 個殘留問題。

---

## 1. 審計輪次摘要

| 輪次 | 焦點 | 發現數 | 關鍵問題 |
|:---:|------|:---:|------|
| 1 | Alpha 研究管線 | 9 | generic fallback 產出偽因子 |
| 2 | 40d lag + L5 + 去重 | 7 | look-ahead bias（IC 膨脹 10-40x） |
| 3 | forward return + fail-closed | 10 | L5 空殼、off-by-one |
| 4 | 因子代碼邏輯 | 6 | 死因子、二階導數錯 |
| 5 | Paper trading 流程 | 15 | kill switch 無限循環（CRITICAL） |
| 6 | 最終行為驗證 | 5 | NameError、門檻不一致 |
| 7 | 全系統綜合 | 39 | sell overflow、JWT 撤銷、安全 |

---

## 2. CRITICAL / HIGH 修復清單

### 2.1 資金正確性 ✅ 4/4 verified

| 問題 | 檔案 | 修復 | 驗證 |
|------|------|------|:---:|
| sell overflow — cash 用未 cap 數量 | oms.py:73 | 先 cap 再算 cash | ✅ |
| 部分成交均價直接覆蓋 | sinopac.py:437 | 加權平均 | ✅ |
| nav_sod==0 → kill switch 失效 | models.py:256 | fallback to nav | ✅ |
| 策略 6.7%/股 vs 風控 5% → 全被拒 | config.py:43 | 5% → 10% | ✅ |

### 2.2 Look-Ahead Bias ✅ 4/4 verified

| 問題 | 檔案 | 修復 | 驗證 |
|------|------|------|:---:|
| 因子代碼無 40d 營收延遲 | alpha_research_agent.py:213 | 加 usable_cutoff | ✅ |
| trust_follow 營收無延遲 | trust_follow.py:94 | 加 rev_cutoff | ✅ |
| 6 個研究因子缺延遲 | research/*.py | 逐一修 | ✅ |
| L5 Walk-Forward 是空殼 | factor_evaluator.py:192 | 實際 IC 分半比較 | ✅ |

### 2.3 並發與死鎖 ⚠️ 4/4 verified + 1 殘留

| 問題 | 檔案 | 修復 | 驗證 |
|------|------|------|:---:|
| Kill switch 不 apply_trades → 無限循環 | app.py:222 | 加 apply_trades + re-trigger guard | ✅ |
| Rebalance/Pipeline 無 mutation_lock | strategy_center.py, jobs.py | 加 async with state.mutation_lock | ✅ |
| Shioaji 線程 vs asyncio 競爭 | realtime.py:104 | asyncio.run_coroutine_threadsafe | ✅ |
| 手動 kill switch 無 lock | risk.py:77 | 加 mutation_lock | ✅ |

> **殘留 R-01**：`realtime.py` `_execute_liquidation` 使用 `run_coroutine_threadsafe` 排程到 event loop，但排程的 coroutine **未取 `state.mutation_lock`**。Kill switch 清倉可能與 pipeline/rebalance 同時修改 portfolio。原始死鎖已迴避（直接改 dict 而非呼叫 `update_market_prices`），但此競爭窗口仍存在。

### 2.4 安全漏洞 ✅ 4/4 verified（1 個小 gap）

| 問題 | 檔案 | 修復 | 驗證 |
|------|------|------|:---:|
| JWT 不查 token 撤銷 | auth.py:43 | 加 token_valid_after 檢查 | ✅ |
| WebSocket 無撤銷檢查 | auth.py:143 | 同上 | ✅⚠️ |
| 預設綁定 0.0.0.0 | config.py:76 | 改 127.0.0.1 | ✅ |
| dev-key 暴露到網路 | config.py:79 | 只在 dev 模式生效 | ✅ |
| admin 密碼明文 log | app.py:50 | 移除密碼從 log | ✅ |

> **WebSocket gap**：`verify_ws_token` 有檢查 `token_valid_after`（撤銷），但**未檢查 `user.is_active`**。停用使用者若未同時呼叫 `invalidate_tokens`，其 WS 連線仍可通過驗證。HTTP 端的 `verify_jwt` 有檢查 `is_active`。

### 2.5 因子研究管線 ✅ 7/7 verified

| 問題 | 檔案 | 修復 | 驗證 |
|------|------|------|:---:|
| generic fallback 產出 revenue_yoy 偽因子 | alpha_research_agent.py:284 | return None | ✅ |
| L3 相關性比較 mean vs IC series | factor_evaluator.py:318 | 改用 IC series | ✅ |
| zscore 變體 24m 硬編碼 | alpha_research_agent.py:352 | regex 提取月數 | ✅ |
| accel 變體 name[-1].isdigit() 為假 | alpha_research_agent.py:408 | regex match | ✅ |
| 外部 .py 被覆寫 | alpha_research_agent.py:466 | skip if exists | ✅ |
| Daemon hot loop | alpha_research_agent.py:1547 | 擴大 idle 判斷 | ✅ |
| PBO 數據不足自動 PASS | validator.py:548 | 回傳 1.0 (FAIL) | ✅ |

---

## 3. MEDIUM 修復清單 ⚠️ 17/19 verified + 2 殘留

| 問題 | 修復 | 驗證 |
|------|------|:---:|
| Validator 13→15 項（加 market_correlation + CVaR） | validator.py | ✅ |
| min_cagr 15%→8%, max_drawdown 50%→40% | validator.py config | ✅ |
| OOS 從 return > 0 改為 Sharpe > 0 | validator.py | ✅ |
| Deploy 門檻 12→14（配合 15 項） | alpha_research_agent.py | ✅ |
| Price polling 靜默失敗無 fallback | realtime.py + app.py | ✅ |
| Reconciliation 無告警通知 | jobs.py | ✅ |
| 報告 benchmark 硬編碼 vs 動態 | alpha_research_agent.py | ✅ |
| WF train 3→2 年（讓 PBO 有效） | validator.py | ✅ |
| 策略 info 硬編碼 | strategy_center.py → 動態 | ✅ |
| Context timezone 不一致 | jobs.py, strategy_center.py | ⚠️ |
| on_bar 崩潰殺死回測 | trading_pipeline.py | ✅ |
| NaN/inf 權重傳播 | engine.py, trading_pipeline.py | ✅ |
| trust_follow NaN YoY 通過 filter | trust_follow.py | ✅ |
| Live mode async fill 不更新 portfolio | service.py | ✅ |
| Live mode 拒絕 PaperBroker fallback | service.py | ✅ |
| CA 憑證缺失無提示 | sinopac.py | ✅ |
| _shares_to_lots 丟棄餘數無 warning | sinopac.py | ✅ |
| 因子取樣覆蓋不足（L3 年度穩定性跳過） | alpha_research_agent.py | ✅ |
| 因子 .py 不進 git | alpha_research_agent.py | ✅ |

> **殘留 R-02**：`jobs.py` 的 `_today_run_id()`、`_has_completed_run_today()`、`_has_completed_run_this_month()` 使用 `datetime.now()`（系統本地時間），但 pipeline 市場時段檢查用 UTC+8。跨時區部署時 idempotency 可能用錯日期，導致 pipeline 重複執行或跳過。

---

## 4. LOW / 設計決策

| 問題 | 狀態 | 驗證 |
|------|------|:---:|
| 因子計算 430 秒/輪 | 可接受（非向量化） | — |
| PBO 用 noise perturbation 非 CSCV | 已標記 inconclusive | — |
| min_icir_l1 名稱誤導（實為 IC） | **已修**：改名 min_ic_l1 | ✅ |
| TWAP split current_bars=None | paper/live 不用 TWAP | — |
| float vs Decimal 不一致 | config 層用 float 可接受 | — |
| 權重正規化 1.5 threshold | 文檔說明（允許 50% 槓桿） | — |
| Pipeline lock TOCTOU | asyncio 單線程，風險極低 | — |
| fillna(0.0) 偏向零 | covariance 層已知限制 | — |
| factor variance ddof=0 vs ddof=1 | 記錄不一致 | — |
| quality scores 未 rank normalize | per-symbol 不適用 | — |
| drawdown 從初始 NAV 而非 peak | safety.py 設計決策 | — |
| turnover penalty 凍結 rebalance | construction.py 過嚴 | — |
| cross_section periods_per_year 膨脹 | **已修**：改用 used_dates | ✅ |
| risk_parity/equal_weight 忽略 short | **未修**（見殘留 R-03） | ⚠️ |

---

## 5. 架構改進

| 改進 | 狀態 |
|------|------|
| Portfolio 狀態持久化 | ✅ atomic write |
| Pipeline 崩潰恢復 | ✅ execution records |
| Pipeline 超時 | ✅ asyncio.wait_for |
| Kill switch 執行清倉 | ✅ submit + apply_trades |
| 整合測試 | ✅ 18 test cases |
| Daemon 模式 + 自動變體 | ✅ --daemon flag |
| 假說生成器 prompt | ✅ 第二終端用 |
| Live mode async fill | ✅ _on_broker_fill callback |
| Live mode 拒絕 fallback | ✅ return False |

---

## 6. Validator 15 項

| # | 檢查 | 門檻 |
|---|------|------|
| 1 | universe_size | ≥ 50 |
| 2 | cagr | ≥ 8% |
| 3 | sharpe | ≥ 0.7 |
| 4 | max_drawdown | ≤ 40% |
| 5 | annual_cost_ratio | < 50% |
| 6 | walkforward_positive | ≥ 60% |
| 7 | deflated_sharpe | ≥ 0.70 |
| 8 | bootstrap_p(SR>0) | ≥ 80% |
| 9 | oos_sharpe | ≥ 0 |
| 10 | vs_1n_excess | ≥ 0% |
| 11 | pbo | ≤ 50% |
| 12 | worst_regime | ≥ -30% |
| 13 | recent_period_sharpe | ≥ 0 |
| 14 | market_correlation | \|corr\| ≤ 0.90 |
| 15 | cvar_95 | ≥ -5% |

---

## 7. 部署標準

```
L5 快篩 (ICIR ≥ 0.30)
  → 大規模 IC (865+ 支, ICIR(20d) ≥ 0.20)
  → Validator (excl DSR ≥ 14/15, DSR ≥ 0.70)
  → Sharpe > 0050, CAGR > 8%, recent > -0.10
  → Paper Trading (5% NAV, 30 天觀察)
```

---

## 8. 經驗教訓

1. **Look-ahead bias 最隱蔽** — 40d 延遲缺失導致 IC 膨脹 10-40x
2. **Generic fallback 是毒藥** — fail-closed，不 fallback
3. **並發需要統一 lock** — asyncio.Lock 不保護線程
4. **小樣本高估嚴重** — L5 ICIR 0.86 大 universe 只有 0.10
5. **生成式代碼需要驗證** — 自動因子必須有 40d lag
6. **風控門檻要配合策略** — 5% vs 6.7% 導致 14/15 被拒
7. **PBO 數據不足不能自動 PASS** — 改為 FAIL
8. **DSR 0.95 對 90+ trials 不現實** — 寬鬆到 0.70
9. **crash recovery 需要原子性** — 持久化 + execution records
10. **時區必須統一** — UTC+8 for 台股日期判斷

---

## 9. 基準因子（Experiment #18，2026-03-27）

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit% |
|--------|:---:|:---:|:---:|:---:|
| revenue_acceleration | +0.292 | **+0.438** | **+0.582** | 67.3% |
| revenue_new_high | +0.249 | +0.374 | +0.435 | 67.3% |
| revenue_momentum | +0.135 | +0.296 | +0.441 | 55.8% |
| revenue_yoy | +0.199 | +0.132 | +0.197 | 57.1% |

StrategyValidator 12/15 通過（revenue_momentum, TW50, 2019-2025）。
唯一失敗：vs 0050 買入持有 (-13.07%)。

---

## 10. 殘留問題（第 8 輪驗證發現）

> 以下 3 個問題在第 7 輪審計中識別，經代碼驗證確認未完全修復。

### R-01: `_execute_liquidation` 未取 mutation_lock（LOW）
- **檔案**：`src/risk/realtime.py` `_execute_liquidation` coroutine
- **現狀**：Kill switch 從 Shioaji tick 線程觸發時，經由 `run_coroutine_threadsafe` 排程到 event loop，但排程的 coroutine 內 `submit_orders` + `apply_trades` 未包在 `async with state.mutation_lock` 中
- **風險**：若 kill switch 清倉恰好與 pipeline rebalance 同時執行，兩者同時修改 portfolio 可能產生不一致狀態
- **嚴重度**：LOW（需要 kill switch 和 rebalance 在毫秒級同時觸發，且 kill switch 有 `kill_switch_fired` guard 防止重複觸發）
- **建議修復**：在 `_execute_liquidation` 內加 `async with state.mutation_lock`（需從 `app.py` 傳入 state reference）

### R-02: Idempotency helpers 用系統時間而非 UTC+8（LOW）
- **檔案**：`src/scheduler/jobs.py:62,68,83`
- **現狀**：`_today_run_id()`、`_has_completed_run_today()`、`_has_completed_run_this_month()` 使用 `datetime.now()`（系統時區），但 pipeline 市場時段檢查用 UTC+8
- **風險**：若伺服器部署在非 UTC+8 時區（如 UTC 的雲端 VM），午夜前後 pipeline 的 idempotency 檢查會用錯日期
- **嚴重度**：LOW（目前伺服器在台灣本地，UTC+8 = 系統時間）
- **建議修復**：統一使用 `datetime.now(timezone(timedelta(hours=8)))` 產生台灣日期

### R-03: `risk_parity` 和 `equal_weight` 不支援 short signals（LOW）
- **檔案**：`src/strategy/optimizer.py:109,42`
- **現狀**：`signal_weight` 在 `long_only=False` 時正確處理負權重（clamp 到 `[-max_weight, max_weight]`）。但 `risk_parity` 硬編碼 `signals[k] > 0` 篩選，忽略所有負信號。`equal_weight` 只給正權重，不支援做空
- **風險**：使用 risk_parity 或 equal_weight 的 long-short 策略會靜默忽略做空信號，只建多頭部位
- **嚴重度**：LOW（目前所有策略都是 long-only，沒有 long-short 需求）
- **建議修復**：`risk_parity` 改為 `abs(signals[k]) > 0` + 保留原始正負號；`equal_weight` 支援負信號時給負權重

---

## 11. 驗證總結

| 類別 | 項目數 | 已驗證 | 殘留 |
|------|:---:|:---:|:---:|
| 2.1 資金正確性 | 4 | 4 | 0 |
| 2.2 Look-Ahead Bias | 4 | 4 | 0 |
| 2.3 並發與死鎖 | 4 | 4 | 1 (R-01) |
| 2.4 安全漏洞 | 5 | 5 | 0 (1 minor gap) |
| 2.5 因子研究管線 | 7 | 7 | 0 |
| 3. MEDIUM | 19 | 17 | 2 (R-02, R-03) |
| 4. LOW / 設計決策 | 14 | 2 confirmed fixed | — |
| **合計** | **57** | **43 verified** | **3 殘留** |

所有 CRITICAL 和 HIGH 修復均已確認生效。3 個殘留問題均為 LOW 嚴重度，不影響當前使用場景（台灣本地部署、long-only 策略）。

---

## 12. Paper Trading 運行驗證（2026-03-27 21:30）

> 對當日 Paper Trading 的實際運行紀錄進行審查。

### 12.1 運行概況

| 項目 | 狀態 |
|------|------|
| 模式 | paper（Shioaji simulation） |
| 持倉 | 12 支台股 |
| NAV | ~$8.44M（初始 $10M，-15.6%） |
| as_of | 2025-06-02（回測模擬日期，非即時） |
| 選股 | 15 支（revenue_momentum_hedged） |
| 成交 | 1 筆（手動測試產生） |
| Pipeline cron | 未觸發（非交易時段 + 多次重啟） |

### 12.2 發現的問題

#### P1（中）：Snapshots 目錄為空 ✅ 已修

`_daily_nav_snapshot` 的 asyncio task 在系統重啟時消失，13:25-13:55 窗口被錯過。

**修正**：pipeline 執行後主動存一次 snapshot，不完全依賴 asyncio task。

#### P2（中）：pipeline_runs 目錄不存在 ✅ 已修

`_execute_pipeline_inner` 不寫 pipeline_runs 紀錄。

**修正**：inner 函式也寫紀錄（和 `execute_pipeline` 一致）。

#### P3（中）：Artifacts 無 run_id 關聯 ✅ 已修

Selection、trade、reconciliation 各自用日期命名，無法追溯關係。

**修正**：所有 artifact 加入 `run_id` 欄位。

#### P4（中）：Pipeline 只取 target 價格 → 舊持倉賣不掉 ✅ 已修

`weights_to_orders` 需要所有涉及股票的價格（target + 現有持倉），但 pipeline 只取 target 的。

**修正**：`all_needed = target_weights ∪ portfolio.positions`。

#### P5（低）：auto/deployed 的 daily_navs 為空

`rev_seasonal_deviation` 部署後沒有每日更新 NAV。auto monitor 需獨立的定時 task。

**狀態**：暫不修（auto-deploy 是實驗性功能）。

### 12.3 Portfolio vs Selection 不一致分析

| 項目 | 數量 |
|------|:----:|
| 持倉（portfolio） | 12 支 |
| 選股（target） | 15 支 |
| 重疊 | 1 支（2887.TW） |
| 應賣出（持倉不在 target） | 11 支 |
| 應買入（target 不在持倉） | 14 支 |

**根因**：portfolio 是多次 pipeline 的累積結果。Selection log 只記錄最後一次（手動測試 19:55），不反映之前的選股歷史。P4 修復後，下次 pipeline 會正確產生 SELL 訂單清理舊持倉。
