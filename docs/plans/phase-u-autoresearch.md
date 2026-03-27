# Phase T：自動因子研究重構（autoresearch 模式）

> 日期：2026-03-27
> 優先級：最高
> 依據：`docs/reviews/autoresearch-alpha/AUTO_ALPHA_PIPELINE_REVIEW.md`

---

## 背景

現有 `alpha_research_agent.py`（1800+ 行）有致命缺陷：
- 假說空間 ~150 個（全部營收），2-4 週後耗盡
- 代碼生成器 40+ if/elif，新因子無法自動實作
- Harvey 修正無限增長，第 500 輪後新因子不可能通過
- 106 個已實作因子只用了 12 個（11% 利用率）

## 目標

採用 Karpathy autoresearch 模式：3 個文件取代 8 個組件。

```
scripts/autoresearch/
├── evaluate.py      ← 固定（READ ONLY）
├── factor.py        ← Agent 唯一可改
├── program.md       ← 研究協議
└── results.tsv      ← 實驗記錄
```

## 執行步驟

### T1：搬移 + 驗證 ✅
- [x] 搬到 `scripts/autoresearch/`
- [x] 修正 evaluate.py 資料載入（parquet 檔名匹配）
- [x] Baseline 跑成功：12-1 momentum, composite_score 8.80

### T2：清理舊系統 ✅
- [x] 刪除舊 agent + 假說模板 + 研究因子文件

### T3：系統整合 ✅
- [x] `POST /auto-alpha/submit-factor` endpoint
- [x] evaluate.py → API → Validator 15 項 → 自動部署
- [x] strategy_builder 支援 3-arg autoresearch 因子
- [x] 代碼安全檢查 + 名稱 sanitization

### T4：Code review + 修復 ✅
- [x] signature mismatch（CRITICAL）
- [x] code sanitization（HIGH）
- [x] 相對路徑 + name sanitization（MEDIUM）

### T5：文檔更新 ✅
- [x] CLAUDE.md
- [x] phase-u-autoresearch.md

## 使用方式

```bash
# 開 Claude Code session
cd D:\Finance
claude -p scripts/autoresearch/program.md

# Agent 自動進入循環：改 factor.py → 跑 evaluate.py → 記錄 → 下一個
```

## 保留的能力

| 能力 | 來源 |
|------|------|
| 15 項 StrategyValidator | `src/backtest/validator.py` |
| 大規模 IC 驗證 | evaluate.py Stage 2 |
| IC-series 去重 | evaluate.py L3 |
| 40 天營收延遲 | evaluate.py 強制 |
| Paper Trading 部署 | 手動，通過因子用 strategy_builder |
| 監控 | `_monitoring_loop` in app.py |

## 丟棄的組件

| 組件 | 原因 |
|------|------|
| `alpha_research_agent.py` | autoresearch 取代 |
| `hypothesis_templates.json` | LLM 自由生成取代 |
| `_implement_revenue_factor()` | Agent 直接寫 factor.py |
| `_generate_parameter_variants()` | Agent 自己決定參數 |
| daemon 模式 | Claude Code session 取代 |
| `experience_memory.py` trajectories | results.tsv + git 取代 |
