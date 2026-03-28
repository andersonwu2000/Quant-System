# Phase AF：結構化記憶 + 因子替換機制

> 來源：AUTORESEARCH_VS_FINLAB_REVIEW_20260329
> FinLab 的 Ralph Loop 記憶系統帶來 3x 效率提升。我們用 20 行 learnings.jsonl 實現 80% 效果。
> 因子替換解決「因子庫飽和後無法改善」的結構性缺陷。

---

## 1. 問題

### 1.1 無記憶 → 重複探索

Agent 每次 session 重啟丟失所有經驗。results.tsv 只記結果，不記原因。
- 不知道「VWAP 偏差和 momentum 高度相關」→ 再試一次
- 不知道「revenue acceleration + momentum confirmation 有效」→ 不會複用

FinLab 消融研究：有記憶 60% 高品質率 vs 無記憶 20%。

### 1.2 只 reject 不 replace → 因子庫飽和

L3 correlation > 0.50 → 直接 reject。隨著因子庫增長，新因子越來越難通過。
但新因子可能比現有因子更好，應該允許替換。

---

## 2. 設計

### 2.1 learnings.jsonl（結構化記憶）

```
watchdog_data/learnings.jsonl    ← evaluator 寫，agent 可讀（透過 evaluator API）
```

每次實驗後 evaluate.py append：
```json
{"ts": "2026-03-29T04:30:00", "direction": "revenue_acceleration", "level": "L4", "icir": 0.51, "status": "keep", "correlates_with": ["revenue_yoy"], "docstring": "3m/12m ratio reflects..."}
{"ts": "2026-03-29T04:35:00", "direction": "vwap_deviation", "level": "L3", "icir": 0.18, "status": "reject", "reason": "corr 0.67 with momentum_12m"}
```

**Agent 怎麼讀？** eval_server.py 新增 `/learnings` endpoint：
```json
GET /learnings → {"successful_directions": [...], "failed_directions": [...], "forbidden": [...]}
```

Agent 在 Docker 模式不能直接讀 watchdog_data。透過 HTTP API 拿到過濾後的摘要。

**資訊洩漏風險：** learnings 包含 ICIR 數值。但這些是 IS 的 ICIR（不是 OOS），和 results.tsv 的 best_icir 一樣。可接受。

### 2.2 因子替換機制

在 evaluate.py 的 L3 correlation check 中加入替換邏輯：

```python
# 現在：
if max_corr > 0.50:
    return L3_FAIL("corr {max_corr} with {correlated_factor}")

# 改為：
if max_corr > 0.50:
    correlated_icir = get_correlated_factor_icir(correlated_factor)
    if new_icir >= 1.3 * correlated_icir and new_icir >= 0.20:
        replace_factor(correlated_factor, new_factor)
        return L3_PASS("replaced {correlated_factor} (ICIR {correlated_icir} → {new_icir})")
    else:
        return L3_FAIL("corr {max_corr}, not better enough to replace")
```

替換時更新 baseline_ic_series.json（dedup 基準）。

---

## 3. 實施步驟

| Step | 內容 | 改動位置 | 工作量 |
|------|------|---------|--------|
| 1 | learnings.jsonl 寫入 | evaluate.py `_make_result()` 後 | 15 行 |
| 2 | `/learnings` API | eval_server.py | 20 行 |
| 3 | program.md 指示 agent 讀 learnings | program.md | 5 行 |
| 4 | 因子替換邏輯 | evaluate.py L3 check | 15 行 |
| 5 | baseline_ic_series 更新 | evaluate.py | 10 行 |
| 6 | 測試 | 手動跑 2-3 因子驗證 | 15 分鐘 |
| **總計** | | | **~1 小時** |

---

## 4. 風險

| 風險 | 緩解 |
|------|------|
| learnings 包含 ICIR → agent 做 adaptive optimization | ICIR 是 IS 數據，不是 OOS。和 results.tsv 風險相同 |
| 替換機制被 game（agent 刻意生成略好的 clone） | 1.3x 門檻 + ICIR ≥ 0.20 基線 |
| learnings 過時（市場 regime 變化） | JSONL append-only，新的覆蓋舊的。可加 TTL |
| evaluator 寫 learnings 到 watchdog_data → work/ 可能意外暴露 | learnings 在 watchdog_data（agent 不可見），API 過濾後才回傳 |

---

## 5. 審批意見（2026-03-29）

### 整體判斷：✅ 方向正確，設計簡潔。3 個改進 + 2 個缺漏。

### 做對了的

1. **learnings.jsonl 而非 SQLite** — 20 行 vs 完整 Agno 框架，符合 LESSONS #16 簡單原則
2. **透過 HTTP API 過濾** — agent 不直接讀 watchdog_data，和 Phase AE 隔離架構一致
3. **1.3× 替換門檻** — 直接採用 FactorMiner 論文的參數（Wang et al., 2026），有學術依據
4. **IS ICIR 不是 OOS ICIR** — 正確識別洩漏風險並判斷為可接受

### 問題 1（HIGH）：替換機制缺少對因子庫整體多樣性的保護

替換邏輯只看「新因子 ICIR ≥ 1.3× 舊因子」。但如果 agent 持續用同一個方向（如 revenue 變體）替換，因子庫最終會全部是 revenue 的高度相關變體。

FactorMiner 有 **Stage 3 批次去重**（批次內相關性 > 0.70 → 剔除），我們沒有。

FactorMiner 的最終因子庫的平均跨因子絕對相關性 |ρ| = 0.203。我們沒有追蹤這個指標。

**建議加一個 post-replace check：**
```python
# 替換後檢查因子庫的平均相關性
avg_corr = compute_avg_pairwise_corr(updated_baseline)
if avg_corr > 0.40:  # 因子庫多樣性退化
    log_warning("Factor library diversity declining: avg |ρ| = {avg_corr}")
    # 不阻擋替換，但在 learnings 中記錄警告
```

工作量：~10 行。

### 問題 2（MEDIUM）：learnings 的 `/learnings` API 回傳太多資訊

計畫 §2.1 設計的 API：
```json
GET /learnings → {"successful_directions": [...], "failed_directions": [...], "forbidden": [...]}
```

如果 `successful_directions` 包含精確的 ICIR 值和 correlates_with 清單，agent 可以精確構建「ICIR 0.51 的因子和 revenue_yoy 相關」的模型 → 專門生成略好於 0.51 的 revenue 變體。

**建議分級回傳：**
```json
{
  "successful_patterns": ["revenue acceleration with momentum filter", "institutional flow momentum"],
  "failed_patterns": ["VWAP deviation variants", "simple delta reversal", "low volatility"],
  "forbidden": ["VWAP variants (corr >0.5 with momentum)", "standardized returns"],
  "stats": {"total_experiments": 47, "l4_pass_rate": "26%", "directions_explored": 8}
}
```

不回傳精確 ICIR 值和 correlates_with。只回傳**方向描述**（從 docstring 提取）和統計摘要。Agent 知道「什麼方向有效」但不知道「精確多有效」。

### 問題 3（MEDIUM）：替換後 baseline_ic_series.json 的更新可能破壞 L3 dedup

替換邏輯：
```python
replace_factor(correlated_factor, new_factor)
# → 更新 baseline_ic_series.json
```

baseline_ic_series.json 用於 L3 去重。如果替換時直接刪除舊因子的 IC series 再加入新因子的，那舊因子的所有「近親」（和舊因子相關 > 0.50 但和新因子可能相關 < 0.50 的因子）會突然變得「可通過 L3」。

**這會導致已被 reject 的因子在替換後重新通過 L3。**

**建議：** 替換時保留舊因子的 IC series 作為 historical record（用 `replaced_by: new_factor_hash` 標記）。L3 dedup 同時檢查 active 和 historical IC series。這樣已 reject 的因子不會復活。

```python
# baseline_ic_series.json 結構改為：
{
  "active": {"factor_hash": [ic_series], ...},
  "historical": {"old_factor_hash": {"series": [...], "replaced_by": "new_hash"}, ...}
}
```

工作量：~15 行。

### 缺漏 1：沒有 learnings 的 TTL/清理機制

計畫提到「可加 TTL」但沒有設計。learnings.jsonl 會無限增長。1000 次實驗後 agent 每次 session 要讀數百行 learnings。

**建議：** `/learnings` API 只回傳最近 100 條 + 所有 forbidden 方向。舊的成功/失敗記錄不刪除（append-only），但 API 做 recency 過濾。

### 缺漏 2：沒有納入 FinLab 的「集中持倉」發現

Review 的 §6 建議測試 8-10 檔集中持倉（FinLab 發現 MDD 從 -55.4% 降到 -33.2%）。但 Phase AF 沒有包含這個測試。

**建議：** 不需要放在 AF（AF 聚焦記憶和替換）。但建議在 revenue_momentum 策略中做一個簡單的 `max_holdings` 參數測試（8 vs 15 vs 20），記錄到研究報告。可以是 AF 之後的獨立實驗。

### 總結

| 項目 | 嚴重度 | 行動 |
|------|:------:|------|
| #1 替換後因子庫多樣性退化 | HIGH | 加 avg_corr 監控（~10 行） |
| #2 /learnings API 回傳過多 | MEDIUM | 只回傳方向描述和統計，不回傳精確 ICIR |
| #3 baseline_ic_series 替換後 dedup 漏洞 | MEDIUM | 保留 historical IC series，dedup 同時檢查 active + historical |
| 缺漏 1: learnings 無 TTL | LOW | API 做 recency 過濾（最近 100 條） |
| 缺漏 2: 集中持倉測試 | N/A | 記錄為獨立實驗，不在 AF 範圍 |

**工作量影響：** 從原本的 ~1 小時增加到 ~1.5 小時。主要是 #1 和 #3 各增加 ~15 行。

## 6. 審批回覆（研究後修正）

### 審批意見全部接受。研究確認每項都有學術/業界依據。

### #1 回覆：多樣性保護 ✅ 接受 — 加 library_health_metrics

研究確認：
- FactorMiner 最終庫 avg |ρ| = 0.203，觀察到 70+ 因子後進入「Correlation Red Sea」
- WorldQuant BRAIN 用 PNL correlation < 0.7 做去重
- 學術共識（Feng, Giglio, Xiu "Taming the Factor Zoo"）：~15 因子足以涵蓋整個 factor zoo

**修正：** 替換後計算 3 個多樣性指標：

```python
def library_health_metrics(ic_series_dict):
    """avg_pairwise_corr, effective_n (eigenvalue), diversity_ratio"""
```

- `avg_pairwise_corr > 0.40` → 警告（不阻擋）
- `diversity_ratio < 0.30` → 阻擋替換
- `effective_n` 記錄到 learnings

**額外發現：** FactorMiner 的替換條件有第三項 — 新因子只能和**恰好一個**已有因子相關。防止一個新因子同時替換多個。我們也應該加這個限制。

### #2 回覆：/learnings API 只回傳方向描述 ✅ 接受

修正 `/learnings` 回傳：

```json
{
  "successful_patterns": ["revenue acceleration with momentum filter"],
  "failed_patterns": ["VWAP deviation variants"],
  "forbidden": ["VWAP variants (corr >0.5 with momentum)"],
  "stats": {"total": 47, "l4_rate": "26%", "directions": 8},
  "library_health": {"avg_corr": 0.18, "effective_n": 12.3, "diversity": 0.77}
}
```

不含 ICIR 數值、不含 correlates_with、不含具體門檻。

### #3 回覆：baseline_ic_series 保留 historical ✅ 接受

研究確認 FactorMiner 也保留 historical baseline。

```json
{
  "active": {"factor_hash": {"series": [...], "icir": 0.42}},
  "archived": {"old_hash": {"series": [...], "replaced_by": "new_hash", "replaced_at": "2026-03-29"}}
}
```

L3 dedup 同時檢查 active + archived。被替換因子的「近親」不會復活。

**研究補充：不自動回溯重新評估被拒因子。** FactorMiner 也不做。靠 agent 下一輪自然重試。但在 learnings 中記錄 `freed_directions`（替換後重新開放的方向），讓 agent 知道可以重試。

### 缺漏 1 回覆：TTL → API recency 過濾 ✅ 接受

`/learnings` 只回傳最近 100 條 + 所有 forbidden。JSONL 本身不刪（append-only audit trail）。

### 缺漏 2 回覆：集中持倉 → 獨立實驗 ✅ 接受

不在 AF 範圍。記錄為後續實驗。

### 修正後的實施步驟（v2）

| Step | 內容 | 工作量 |
|------|------|--------|
| 1 | learnings.jsonl 寫入（evaluate.py _make_result 後） | 15 行 |
| 2 | `/learnings` API（eval_server.py，只回傳方向描述） | 25 行 |
| 3 | program.md 指示 agent 讀 learnings | 5 行 |
| 4 | 因子替換邏輯（L3 check，限一對一替換） | 20 行 |
| 5 | baseline_ic_series active/archived 結構 | 15 行 |
| 6 | library_health_metrics（avg_corr, effective_n, diversity_ratio） | 25 行 |
| 7 | 替換後 diversity check（阻擋 ratio < 0.30） | 10 行 |
| 8 | freed_directions 記錄 + learnings 更新 | 10 行 |
| 9 | 測試：模擬替換 + 多樣性退化場景 | 20 分鐘 |
| **總計** | | **~2 小時** |

## 7. 第二輪審批（2026-03-29）— 方法論與過擬合焦點

### 整體：§6 回覆品質好，多樣性保護和 historical baseline 設計正確。但有 2 個方法論問題。

### 問題 A（HIGH）：替換機制加速 holdout 降解

**現狀：** L5 OOS 驗證用 Thresholdout 保護，每次查詢消耗 ~0.7 bits holdout budget。我們已經用了 233 次（Dwork budget 超出 62 倍）。

**AF 的影響：** 替換機制讓原本在 L3 就被 reject 的因子（高相關性）現在可以進入 L4/L5。每個「替換候選」都會多跑一次 L5 OOS 查詢。

**量化：** 假設因子庫有 15 個 active 因子。原本 L3 reject rate ~60%（233 次中約 140 次在 L3 停止，沒進入 L5）。替換機制讓其中一部分（ICIR ≥ 1.3× 的子集）進入 L5。估計額外增加 10-20% 的 L5 查詢量。

在 holdout 已經嚴重降解的情況下，**每增加一次 L5 查詢都是有代價的**。

**建議：**
- 替換候選**不跑 L5** — 只用 L1-L4 的 IS 指標判斷是否替換
- 理由：替換的目的是改善因子庫品質（IS 維度），不是驗證 OOS 有效性。如果新因子的 IS ICIR ≥ 1.3× 舊因子，它在 IS 上就是更好的。OOS 驗證留給最終部署前的 paper trading
- 這也和 FACTOR_PIPELINE_DEEP_REVIEW 的結論一致：「不要再消耗 holdout，paper trading 才是真正的驗證」

```python
# 替換邏輯只用 IS 指標，不觸發 L5
if max_corr > 0.50:
    if new_icir >= 1.3 * correlated_icir and new_icir >= 0.20:
        # 替換（不跑 L5，不消耗 holdout budget）
        replace_factor(...)
        return L3_REPLACED  # 新的 level 狀態
    else:
        return L3_FAIL
```

### 問題 B（HIGH）：learnings 的「成功模式」會引導 agent 集中探索 → 加劇 multiple testing

**現狀的探索模式：**
- 無記憶 → agent 隨機探索 → 方向多樣但低效
- 有記憶 → agent 集中探索成功方向 → 高效但多樣性降低

**FinLab 聲稱 3x 效率。但 3x 效率 = 3x 的方向集中度。**

如果 learnings 說「revenue acceleration 有效」，agent 會生成 30 個 revenue acceleration 變體。其中可能有 5 個通過 L4 — 但它們不是 5 個獨立假說，它們是同一個假說的 5 個變體。DSR 的 N 應該算 1 不是 5。

**這直接加劇 multiple testing 問題：**
- 表面上：50 個實驗，15 個通過，看起來 30% pass rate
- 實際上：50 個實驗只有 5 個獨立方向，15 個「通過」的都是 revenue 變體
- DSR N=5 下的噪音期望 Sharpe ≈ 1.1 — 和我們觀測的 0.94 差不多

**FinLab 沒有 Thresholdout，沒有 DSR，沒有 Factor-Level PBO。他們的 3x 效率可能部分來自 overfitting to in-sample patterns。**

**建議：**

1. learnings 的 `successful_patterns` 必須標註「已探索深度」：
```json
{
  "successful_patterns": [
    {"direction": "revenue acceleration", "variants_tried": 12, "variants_passed": 3, "saturation": "HIGH"},
    {"direction": "institutional flow", "variants_tried": 2, "variants_passed": 1, "saturation": "LOW"}
  ]
}
```

2. program.md 加入明確指引：
```
When a direction shows saturation >= HIGH (5+ variants tried),
move to a DIFFERENT direction. Diminishing returns are real.
```

3. Phase AB 的 Factor-Level PBO 已經用「獨立假說聚類」來修正 N。確認 AF 的替換不會繞過這個修正（替換後的因子仍然要被計入 PBO 的 N 中）。

### 問題 C（LOW）：diversity_ratio < 0.30 的阻擋門檻缺乏依據

§6 #1 回覆設了 `diversity_ratio < 0.30 → 阻擋替換`。但 0.30 的來源是什麼？

- FactorMiner 的 avg |ρ| = 0.203 → diversity 高
- Feng et al. 說 ~15 因子涵蓋 factor zoo → 但沒給 diversity ratio 門檻
- 0.30 看起來像拍腦袋

**建議：** 先不阻擋，只警告。收集 10-20 次替換的數據後，用經驗分佈校準門檻。過早設硬門檻可能阻止合法的替換。

```python
# 暫時只警告不阻擋
if diversity_ratio < 0.30:
    log_warning("Low diversity")
    # 記錄到 learnings 但不阻擋替換
```

### 總結

| 問題 | 嚴重度 | 核心 | 行動 |
|------|:------:|------|------|
| A: 替換加速 holdout 降解 | **HIGH** | 替換候選不該跑 L5 | 替換只用 IS 指標（L1-L4），不觸發 L5 |
| B: 記憶引導集中探索 → multiple testing | **HIGH** | 3x 效率可能 = 3x 方向集中度 | learnings 標註方向飽和度 + program.md 指引分散探索 |
| C: diversity_ratio 0.30 無依據 | LOW | 門檻拍腦袋 | 先警告不阻擋，收集數據後校準 |

### 獨立驗證回覆（2026-03-29）

#### A 回覆：**部分不同意 — 替換候選仍應跑 L5**

審批前提「holdout 嚴重降解（233 次）」是舊研究週期的數字。當前週期：
- L5 query count ≈ 30，不是 233
- Thresholdout 有效 budget = O(n) ≈ 375，不是 Dwork 的 4
- 替換額外增加 ~10-20% → ~36 次，遠在 budget 內

**不跑 L5 的風險更大：** 用 IS-overfit 因子替換 OOS 穩定因子 → 因子庫品質下降。一個 IS ICIR 0.65 但 OOS 崩潰的因子，會替換掉 IS ICIR 0.50 但 OOS 穩定的因子。

**折衷：** 替換候選跑 L5，但加上限 — 每輪研究最多 10 次替換嘗試。

```python
MAX_REPLACEMENTS_PER_CYCLE = 10
if replacement_count >= MAX_REPLACEMENTS_PER_CYCLE:
    return L3_FAIL("replacement budget exhausted")
```

#### B 回覆：**部分同意 — 區分兩種記憶功能**

審批把兩種功能混在一起了：
- **(a) 避免死路** (forbidden zones) — 純收益，FinLab 冗餘拒絕率 43.8% → 55.2%
- **(b) 集中好方向** (success patterns) — 有風險，加劇方向集中

FinLab 的 3x 效率**主要來自 (a)**（避免重複探索死路），不是 (b)。

且 Factor-Level PBO 已經用獨立假說聚類修正 N — 30 個 revenue 變體只算 1 個方向。Multiple testing 已被處理。

**修正：** learnings 的 `/learnings` API 強調 forbidden zones，success patterns 附帶 saturation 標記（接受審批建議）但不壓制：

```json
{
  "forbidden": ["VWAP variants", "simple delta reversal"],  // 主要功能
  "successful_patterns": [
    {"direction": "revenue accel", "saturation": "HIGH", "variants_tried": 12},
    {"direction": "institutional flow", "saturation": "LOW", "variants_tried": 2}
  ],
  "guidance": "Explore LOW saturation directions first"
}
```

#### C 回覆：**部分同意 — 雙門檻**

0.30 確實需要校準。但「只警告不阻擋」等於沒牙齒。

模擬：FactorMiner avg |ρ| = 0.203、15 因子 → diversity_ratio ≈ 0.53-0.67。0.30 其實很寬鬆。

**修正：** 雙門檻
- `diversity_ratio < 0.30` → **WARN**（記錄到 learnings）
- `diversity_ratio < 0.15` → **BLOCK**（嚴重退化，15% 方差獨立 = 因子庫幾乎全部冗餘）

## 8. 參考

- Wang et al. (2026). FactorMiner. arXiv:2602.14670 — 替換條件 Eq.11, 1.3x ICIR, 一對一限制
- WorldQuant BRAIN IQC — PNL corr < 0.7, Sharpe 10% 提升
- AlphaForge (AAAI 2025) — diversity loss 在生成階段控制多樣性
- Feng, Giglio, Xiu — "Taming the Factor Zoo" — ~15 因子涵蓋 zoo
- FactorMiner 消融研究 — 70+ 因子後 Correlation Red Sea
- A-Mem (2025) — 自主記憶管理（自動描述 + 關聯 + 演化）
- Graph Memory (2025) — 軌跡蒸餾為 meta-cognitive strategies
