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

### T1：搬移 + 驗證（30 min）
- [ ] 從 `docs/reviews/autoresearch-alpha/` 搬到 `scripts/autoresearch/`
- [ ] 產出 `data/research/baseline_ic_series.json`
- [ ] 產出 `data/research/universe.txt` + `large_universe.txt`
- [ ] 驗證 `python scripts/autoresearch/evaluate.py` 端到端可執行

### T2：清理舊系統（30 min）
- [ ] 刪除 `scripts/alpha_research_agent.py`
- [ ] 刪除 `data/research/hypothesis_templates.json`
- [ ] 刪除 `data/research/memory.json`
- [ ] 刪除 `src/strategy/factors/research/rev_*.py`
- [ ] 刪除 `scripts/hypothesis_generator_prompt.txt`
- [ ] 刪除 `scripts/generate_hypotheses.md`
- [ ] 保留 `src/alpha/auto/factor_evaluator.py`（evaluate.py 整合了其邏輯）
- [ ] 保留 `src/alpha/auto/strategy_builder.py`（通過因子仍需包裝）
- [ ] 保留 `src/backtest/validator.py`（最終 15 項驗證）

### T3：首次 baseline run（15 min）
- [ ] 跑 `python scripts/autoresearch/evaluate.py`
- [ ] 確認輸出 composite_score
- [ ] 初始化 `results.tsv`

### T4：更新系統文檔（15 min）
- [ ] 更新 `CLAUDE.md` — Auto-Alpha Research Pipeline 段落
- [ ] 更新 `docs/claude/EXPERIMENT_STANDARDS.md` — 因子研究管線
- [ ] 更新 `docs/claude/ARCHITECTURE.md` — 排程段落
- [ ] 更新 `docs/ARCHITECTURE_REVIEW_2026Q1.md` — Phase T 狀態

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
