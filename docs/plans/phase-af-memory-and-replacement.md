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

**獨立驗證：** 方向正確。當前因子庫只有 2 個 active 因子，但研究正在跑（100+ 實驗、30+ L5 通過），因子庫增長可能很快。**等到 15+ 再加 = 來不及。avg_corr 監控必須在 AF 一起實作。**

另外注意：1.3× 門檻來自 FactorMiner 的 **IC**（非 ICIR）。我們用 ICIR（更嚴格，要求穩定性），但 1.3× 這個數字沒有直接的 ICIR 校準依據。作為起點可接受，後續用數據校準。

接受建議：加 avg_corr 監控。

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

**獨立驗證：部分不同意。**

審批說「被替換因子的近親復活是壞事」。但反例：
- B = revenue_yoy，D = revenue_acceleration（替換 B）
- E = revenue_growth_3m，和 B 高相關但和 D 可能不相關
- E 復活是合理的 — E 和 D 捕捉不同的信號面向

**保留 historical 做 dedup 是過度保守** — 它阻止了合法的新因子進入。

**修正方案：** 只用 active 做 dedup（不保留 historical）。替換後在 learnings 記錄 freed_directions，讓 agent 知道哪些方向重新開放。Factor-Level PBO 會在因子庫層面捕捉整體過擬合風險。

如果未來發現復活的因子確實都是 clone → 再加回 historical dedup。

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

## 8. 最終審批（2026-03-29）

### 判定：✅ 核准執行。附 3 個條件。

兩輪審批（§5, §7）提出 6 個問題，§6 和 §8 的回覆都合理。分歧已在折衷方案中解決。以下是最終判定：

### 已解決的分歧（不再追蹤）

| 分歧 | 折衷方案 | 判定 |
|------|---------|------|
| baseline 保留 historical vs 只用 active | 只用 active + PBO 捕捉整體風險 | ✅ 接受作者方案。如果 clone 復活 → 再加 historical |
| 替換是否跑 L5 | 跑 L5 但上限 10 次/週期 | ✅ 合理折衷。30+10=40 次仍在 Thresholdout budget 內 |
| diversity_ratio 門檻 | 0.30 WARN / 0.15 BLOCK | ✅ 雙門檻比單門檻好。0.15 BLOCK 有安全底線 |
| 記憶 vs multiple testing | forbidden zones 為主 + saturation 標記 | ✅ 正確區分了兩種記憶功能 |

### 核准條件（必須在實作時滿足）

**條件 1：replacement_count 必須記錄到 learnings.jsonl 和 l5_query_count.json**

§8 回覆說「最多 10 次替換嘗試」，但沒有說這個 counter 存在哪裡、怎麼重置。

要求：
- `replacement_count` 和 `l5_query_count` 一起存在 `watchdog_data/l5_query_count.json`
- 每輪研究重置（和 L5 budget 生命週期一致）
- `/learnings` API 回傳 `replacement_budget_remaining`

**條件 2：saturation 必須在 evaluator 強制，不是 prompt 建議**

§8 寫了 `"guidance": "Explore LOW saturation directions first"`。但 LESSONS #1 說「agent 的安全靠隔離不靠指令」。

**獨立驗證修正：** 原審批建議「docstring 方向名 + L0 阻擋」不可靠 — agent 控制 docstring，改一個詞就繞過。且 L0 沒有 IC series 數據。

修正為：**L3 correlation-based saturation**。如果新因子和某個 active 因子 corr > 0.50，且該 active 因子已被匹配 >= 10 次 → L3 fail（除非符合 1.3× 替換條件）。用實際數據判定，agent 無法繞過。

```python
# 在 L3 dedup check 中：
if max_corr > 0.50:
    match_count = get_match_count(most_correlated_factor)  # 從 learnings 讀
    if match_count >= 10 and not meets_replacement_criteria(new_icir, correlated_icir):
        return L3_FAIL("direction saturated: {match_count} variants tried for {most_correlated}")
```

**條件 3：第一次替換前必須手動確認因子庫狀態**

替換機制是不可逆的（被替換的因子從 active 移除）。在自動化之前：
- 確認 `baseline_ic_series.json` 的 active 因子數量和內容
- 確認 `library_health_metrics` 的 baseline 值
- 手動跑一次替換流程（用已知因子對）驗證邏輯正確

### 最終實施步驟（v3）

| Step | 內容 | 來源 | 狀態 |
|------|------|------|:----:|
| 1 | learnings.jsonl 寫入 | §2.1 | ✅ |
| 2 | `/learnings` API（方向描述 + saturation + forbidden） | §6 #2 | ✅ |
| 3 | program.md 加 learnings 讀取指引 | §3 | ✅ |
| 4 | 因子替換邏輯（L3，一對一，1.3× ICIR，跑 L5） | §2.2 + §8 A | ✅ |
| 5 | replacement_count + l5_query_count 合併追蹤 | 條件 1 | ✅ |
| 6 | library_health_metrics（avg_corr, effective_n, diversity_ratio） | §6 #1 | ✅ |
| 7 | diversity 雙門檻（0.30 WARN / 0.15 BLOCK） | §8 C | ✅ |
| 8 | direction saturation 強制限制（L3 correlation-based, match >= 10） | 條件 2 | ✅ |
| 9 | eval_server.py 加 library_health + replacement_budget | 條件 1 | ✅ |
| 10 | 手動驗證替換流程 | 條件 3 | ✅ 端到端測試通過 + baseline 讀寫分離修正 |

### 風險追蹤清單

以下項目在實作後觀察，每月覆核：

| 項目 | 觀察指標 | 行動觸發條件 |
|------|---------|-------------|
| 1.3× ICIR 門檻是否合適 | 替換次數 / 替換成功率 | 成功率 < 30% → 降到 1.2×；> 80% → 升到 1.5× |
| clone 復活問題 | 替換後 L3 通過率是否異常升高 | L3 pass rate 突增 > 50% → 加回 historical dedup |
| 記憶導致方向集中 | learnings 中 directions_explored 的增長速度 | 連續 20 個實驗只有 ≤ 2 個方向 → 檢查 saturation 機制 |
| L5 query budget | l5_query_count.json | 單週期超過 50 → 暫停研究 |

## 9. Code Review（2026-03-29）

### 範圍：evaluate.py（258 行新增）、eval_server.py（26 行新增）、program.md（6 行變更）

### CRITICAL（0 個）

無。

### HIGH（1 個）

**AF-H1：`_write_learning` 洩漏 `best_icir` 精確值到 learnings.jsonl**

`evaluate.py:1123` 寫入 `"best_icir": round(results.get("best_icir", 0), 4)`。eval_server.py 的 `/evaluate` 已改為 bucket（strong/moderate/weak/none），但 learnings.jsonl 仍存精確值。

- Docker 模式：✅ 安全（agent 看不到 watchdog_data/）
- Host 模式（fallback）：⚠️ agent 可直接讀 learnings.jsonl

**建議：** learnings.jsonl 也改為 bucket。目前不阻塞（Docker 是主要模式）。

### MEDIUM（3 個）

**AF-M1：direction 提取邏輯脆弱**（evaluate.py:1110-1114）

從 factor.py 第一個「非 import/def/comment」行提取方向名。多行 docstring 可能取到第二行。不會 crash，但 direction 可能不準確。影響小。

**AF-M2：`_replace_factor` 用 timestamp 命名**（evaluate.py:513）

`f"factor_{time.strftime('%Y%m%d_%H%M%S')}"` — 同秒替換兩次會 name 衝突。實際風險極低（evaluate 是 sequential）。

**AF-M3：bucket 邊界分散在 eval_server.py 各處**

`/evaluate` 的 ICIR bucket（0.10/0.20/0.40）和 `/learnings` 的 saturation（5/10）定義在不同位置。建議抽成 eval_server.py 頂部常量。

### LOW（1 個）

**AF-L1：eval_server.py 的 `open()` 未用 `with`**（line 36, 72）

File handle 依賴 GC 關閉。影響極小。

### 端到端測試修正（2026-03-29）

測試發現 baseline_ic_series.json 在 Docker 的 `data/research/` 是 ro mount，替換寫入會失敗。

修正：讀寫路徑分離 — `_dedup_read_path()`（優先 watchdog_data/ rw，fallback data/research/ ro）、`_dedup_write_path()`（永遠寫 watchdog_data/）。

### 審批條件驗證

| 條件 | 狀態 |
|------|:----:|
| 1. replacement_count 在 l5_query_count.json + `/learnings` 回傳 budget | ✅ 已實作 |
| 2. saturation 在 evaluator 強制（L3 match_count >= 10 → fail） | ✅ 已實作 |
| 3. 首次替換前手動驗證 | ✅ 端到端測試已通過 |

### 總結

| 嚴重度 | 數量 | 行動 |
|:------:|:----:|------|
| HIGH | 1 | AF-H1：host 模式限定，Docker 安全。建議後續改為 bucket |
| MEDIUM | 3 | 不阻塞，後續改善 |
| LOW | 1 | 清理即可 |

**整體品質：好。** 核心邏輯（替換、多樣性、saturation、learnings）正確。3 個審批條件全部滿足。`/evaluate` 主動改為 bucket 模式超出計畫要求。baseline_ic_series 讀寫分離是端到端測試的正確修正。

## 10. 參考

- Wang et al. (2026). FactorMiner. arXiv:2602.14670 — 替換條件 Eq.11, 1.3x ICIR, 一對一限制
- WorldQuant BRAIN IQC — PNL corr < 0.7, Sharpe 10% 提升
- AlphaForge (AAAI 2025) — diversity loss 在生成階段控制多樣性
- Feng, Giglio, Xiu — "Taming the Factor Zoo" — ~15 因子涵蓋 zoo
- FactorMiner 消融研究 — 70+ 因子後 Correlation Red Sea
- A-Mem (2025) — 自主記憶管理（自動描述 + 關聯 + 演化）
- Graph Memory (2025) — 軌跡蒸餾為 meta-cognitive strategies
