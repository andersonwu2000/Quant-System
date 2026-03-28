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
