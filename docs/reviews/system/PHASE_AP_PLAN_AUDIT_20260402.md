

## 6b. 審計補充意見（2026-04-02）

以下意見不是新增 scope，而是修正本文件本身的錯誤假設，避免後續按錯誤路徑執行：

1. **AP-C1 的 bug 描述需修正**
   - 問題是 `eval_server.py` 的 library metadata 寫入會因未定義區域變數而靜默失敗。
   - 不是「吃到上一次 evaluate 的值」。

2. **AP-1 目前引用了不存在的切入點**
   - `evaluate.py` 主線資料組裝不是 `_build_factor_data()`，而是 `_load_all_data()`、`_mask_data()`，以及 Validator 路徑內部的 `_FactorStrategy` 再次拉 Context 資料。
   - 實作前需先更新設計文件中的切入函式，否則工時與影響範圍會被低估。

3. **AP-2 不能以 `/run-now` 當主要證據**
   - `/run-now` 目前是 `AlphaResearcher + AlphaScheduler` 路線，不是 `factor_evaluator.py` 的直接呼叫點。
   - 正確做法是先 inventory 所有 call-sites，再決定 legacy 下線策略。

4. **AP-3 的驗收條件依賴 schema 先改**
   - 現有 stub endpoint 有嚴格 `response_model`。
   - 若不先修改 schema，直接在 response 加 `"status"` 或 `"warning"`，客戶端不會看到。

5. **AP-16 單改 `program.md` 不足以防止 reverse-engineering**
   - evaluator 的 `/evaluate`、`/learnings` 本身也暴露 bucket 與 library health。
   - 若此項要做，應定義完整資訊暴露面，而不是只做 prompt 去具體化。

6. **本文件中「AutoResearch 是因子產出的唯一管線」表述過滿**
   - 現況下 AutoResearch 是新因子畢業主線，但 `src/alpha/auto/` 仍有既有因子池研究與生產引擎角色。
   - 建議後續文件統一表述為：AutoResearch 是新因子工廠主線；AutoAlpha 是既有因子池的研究/執行引擎。

這些修正應視為 AP 開工前的文件清理，不應等到實作中途才發現。

## 6c. 第二輪審計（2026-04-02，Claude Opus 4.6）

本輪審計範圍：(1) 逐一比對 `AUTO_RESEARCH_REVIEW.md` 30+ 條建議 vs AP 現有項目的覆蓋缺口；(2) 代碼驗證計畫中的事實宣稱；(3) 優先級與風險排序合理性。

### A. 覆蓋缺口 — Review 建議未被 AP 納入的 16 項

下表列出 Review 中明確的建議但在 AP 中沒有對應 item 的項目。建議挑選 ★ 項目補入 P1 或新建 AP-17~AP-22。

| # | Review 章節 | 建議摘要 | 嚴重度 | 是否應補入 |
|---|------------|---------|--------|-----------|
| ★1 | §1.1 | Composite score 公式重構（改 Pareto front 或 rank-weighted） | Medium | 建議補入 P2，影響 agent 的選擇壓力方向 |
| ★2 | §1.3.2 | Thresholdout noise scale 應按 IC_std 動態調整，固定 0.05 保護力不足 | Medium | **建議補入 P1**，直接影響 L5 holdout 有效性 |
| ★3 | §1.3.3 | Thresholdout seed 移除 factor_hash，改用 evaluator-only secret salt | Medium | **建議補入 P1**，與 AP-C3 同屬 Thresholdout 修復 |
| ★4 | §1.4.2 | OOS window 每次 evaluate 重算導致非確定性，應 session-level 固定 | Medium | **建議補入 P1**，改動小但影響結果可重現性 |
| 5 | §1.6 | Industry neutralization 用股票代碼前 2 碼太粗糙，應用 TWSE 分類 | Medium | 可併入 AP-1 FactorDataBundle |
| ★6 | §2.1 | Evaluator healthcheck 只 ping `/health`，應加數據可用性 + watchdog timer | High | **建議補入 P1（新項 AP-17）** |
| 7 | §2.3 | Windows volume mount 無真實 POSIX permission；work/.git 暴露歷史 | Medium | 可併入 AP-12 git 治理 |
| 8 | §3.1 | Dockerfile.evaluator 加 `chmod 444 /app/evaluate.py`（defense in depth） | Low | 可併入 AP-12 |
| ★9 | §3.2 | Agent 可推測 OOS dates（today - 90 - 548）；應加 KS test + 隨機化 offset | Medium | **建議補入 P1（新項 AP-18）** |
| 10 | §4.1 | Evaluator 應 sync 寫 results.tsv；agent 啟動時讀 learnings API 而非 results.tsv | Medium | 可併入 AP-4 Runbook 操作規範 |
| 11 | §4.2 | Watchdog stale 門檻 30 min 太粗，應監控 evaluator active request | Low | 可併入 AP-17 evaluator 監控 |
| 12 | §4.3 | 缺少 API token cost tracking | Medium | 建議補入 P2（新項 AP-19） |
| 13 | §4.4 | Deploy queue 缺 size alert + host cron 消化 | Medium | 建議補入 P2 |
| ★14 | §5.3 | 80 行限制應補 AST cyclomatic complexity check | Medium | **建議補入 AP-6 擴展** |
| ★15 | §6.2 | Universe survivorship bias — 需歷史 universe 快照 | High | **建議補入 P1（新項 AP-20）**，AP-1 DataBundle 不解決此問題 |
| 16 | §7.2 | Watchdog `_process_pending()` 一次只處理一個 marker | Low | 可併入 P2 |

**小結：** 16 項缺口中，★ 標記的 8 項建議在 P0/P1 階段處理（其中 3 項可合併到現有 AP item，5 項需新建）。

### B. 優先級錯配

| AP Item | 計畫優先級 | 建議優先級 | 原因 |
|---------|-----------|-----------|------|
| AP-12（git allowlist） | P1（2-4 週） | **應升至 P0** | 當前 blocklist 至少有 5 種繞過路徑（`checkout -- .`、`stash`、`rebase --abort`、直接呼叫 `/usr/local/lib/git-safe/git`、Python subprocess）。改動量小（rewrite 一個 shell script），影響面限 agent Dockerfile |
| AP-13（credentials ro） | P1（2-4 週） | **應升至 P0** | 只需改 docker-compose.yml 一行（加 `:ro`），零風險零衝突。OAuth token 暴露是真實攻擊面 |
| AP-15（Stage 2 _close_matrix） | P1（2-4 週） | 可維持 P1 | 影響效能但不影響正確性（fallback path 正確但慢） |

### C. 代碼事實驗證

以下是對計畫中宣稱的逐項驗證結果：

| 宣稱 | 驗證結果 | 影響 |
|------|---------|------|
| AP-C1：eval_server.py `ic_source`/`ic_trend`/`best_horizon` 在 line 263-268 才定義 | **確認**。Line 252-254 引用未定義變數，在 try/except 中觸發 NameError 被吞掉。library metadata save 靜默失敗 | 第一輪審計的修正描述正確 |
| AP-C2：ensemble 只檢查 L2 | **確認**。`eval_server.py:427-430` 只有 `median_icir >= 0.30` 判斷，無 L3/L4/L5 | — |
| AP-C3：L5 budget 只印 warning | **確認**。`evaluate.py:1488-1490` `print(..., file=sys.stderr)`，無 block 邏輯 | — |
| AP-1：evaluate.py 的資料組裝函式是 `_build_factor_data()` | **不存在**。實際是 `_load_all_data()` + `_mask_data()`。第一輪已指出 | 計畫 §1 AP-1 描述「修改範圍」第 4 點仍寫 `_build_factor_data()` |
| AP-2：factor_evaluator.py 仍有 callers | **無 caller**。grep 全 codebase 只有 evaluate.py 中的註釋引用（`# from legacy factor_evaluator.py`）。零 import、零 call-site | 可直接標 deprecated + 移入 archive，不需 call-site inventory |
| AP-3：stub endpoints 有嚴格 response_model | **確認**。`/safety-gates` 回傳硬編碼 `all_clear=True`；`/factor-pnl` 回傳 `[]`；`/factor-pool` 回傳空 active_factors | — |
| AP-6：`/submit-factor` 只靠 regex | **確認且比描述更嚴重**。`FORBIDDEN_PATTERNS` 是字串匹配，可被 `__import__('os')` 繞過 | AP-6 的 AST 方案正確但應提升優先級 |

### D. 計畫自身的文件品質問題

1. **AP-1 修改範圍仍引用不存在的函式名**
   - §1 AP-1 第 4 點寫「`scripts/autoresearch/evaluate.py`：`_build_factor_data()` 改為呼叫 `build_factor_data()`」
   - 實際切入點是 `_load_all_data()` (line 224) + `_mask_data()` (line 359)
   - 第一輪 6b.2 已指出但正文未修正。**建議在開工前更新正文**

2. **AP-2 的 call-site inventory 結論已出**
   - 第一輪 6b.3 建議「先 inventory 所有 call-sites」。現已驗證：**零 call-site**
   - 可簡化為：直接在檔案頂部加 deprecation warning + 移入 `src/alpha/auto/archive/`
   - 不需要漸進式下線策略

3. **AP-14 的 penalty 方案需更精確**
   - 計畫寫「Bonferroni `/ sqrt(5)` 或使用 effective variants count」
   - Bonferroni correction 不是除以 `sqrt(N)` 而是除以 `N`（i.e., ICIR threshold 乘以 5）。`sqrt(N)` 是 Sidak correction 或 random search 的近似
   - 建議明確：(a) 固定用 rank normalization（最簡單，消除自由度），或 (b) 用 `max(5 variants) / sqrt(2 * ln(5))` (Bonferroni-Holm 近似)

4. **施做順序圖漏項**
   - §4 的施做順序圖未包含 AP-C1~C3（雖然文字說「立即修」，但圖中跳過直接從 P0 開始）
   - 建議把 Critical Bugs 明確畫入流程圖第一行

5. **成功標準缺少量化指標**
   - Must-have 條件中，「跨入口一致性測試通過」「endpoint 標記 experimental」是 binary check
   - 缺少可度量的回歸防護：例如「現有 L4+ 因子在新 bundle 下 ICIR 變動 < 5%」「ensemble endpoint 返回 501 或跑完整 gate」

### E. 新增項目建議

基於覆蓋缺口分析，建議新增以下項目：

**AP-17：Evaluator 健康監控強化**（P1）
- healthcheck 加入數據載入驗證（不只 `/health` ping）
- evaluate timeout 加入 process-level kill（目前只有 subprocess 5 min timeout，Flask 本身無防護）
- watchdog 監控 evaluator 的 last_request_time

**AP-18：OOS 確定性與反逆推**（P1）
- OOS window 在 session 啟動時固定（寫入 watchdog_data），不隨日期滾動
- evaluate.py 加入 factor output KS test：IS 期間與 OOS 期間的 factor value 分佈差異 > 0.3 → 自動 reject
- OOS offset 加入 ±30 天隨機化

**AP-19：Token Cost Tracking**（P2）
- status.ps1 從 agent container 日誌提取 token 消耗
- 設定每 session 的 spending alert threshold

**AP-20：Universe Survivorship Bias**（P1）
- 建立月度歷史 universe 快照（從 TWSE 上市/上櫃名單或 finmind 數據）
- IC 計算時用 as_of 日期對應的 universe 而非靜態 universe.txt
- 此項獨立於 AP-1，因為 DataBundle 統一格式不等於統一 universe

**AP-21：Thresholdout 強化**（P1，合併 AP-C3 的後續）
- noise scale 改為 `0.2 * np.std(ic_series_20d)` 動態計算
- seed 移除 factor_hash，改用 evaluator 啟動時生成的 session-level random salt（存 watchdog_data，agent 不可見）
- budget 200 改為 hard block（AP-C3 已處理 warning→block，此項追加 noise + salt 修復）

### F. 結論

Phase AP 的整體框架正確，Critical Bugs 識別準確，P0 四項（FactorDataBundle、降級 evaluator、stub 清理、Runbook）是合理的治理基礎。主要問題：

1. **覆蓋率 ~60%** — Review 30 條建議中有 16 條未被納入，其中 8 條值得在 P0/P1 處理
2. **AP-12、AP-13 應升至 P0** — 改動量極小（一行 yml + 一個 shell script），風險極低
3. **計畫正文有 3 處事實錯誤未修正**（`_build_factor_data()`、factor_evaluator call-site inventory、Bonferroni `sqrt` 公式）
4. **缺少 5 個新項目**（AP-17~AP-21），建議在開工前補入

建議在開工前做一次文件清理 pass：修正正文中的函式名引用、更新 AP-2 為「直接標 deprecated」、修正 AP-14 的統計公式、把施做順序圖補齊 Critical Bugs。