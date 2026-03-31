# Autoresearch 操作指南

## 架構

```
agent 容器            evaluator 容器         watchdog 容器
(Claude Code)        (Flask HTTP)           (背景驗證)
  │                     │                      │
  │ 改 factor.py        │                      │
  │ curl /evaluate ────→│ 跑 evaluate.py       │
  │ ←── pass/fail ──────│                      │
  │                     │ 寫 factor_returns/ ──→│ 累積 20+ 後算 PBO
  │ curl /learnings ───→│ 回傳經驗摘要         │
  │                     │                      │ Validator 16 checks
  │                     │                      │ Factor-Level PBO
```

3 個 Docker 容器 + 共享 volume：
- **agent**：只有 work/（factor.py + results.tsv）+ data/yahoo,finmind,twse,finlab（ro）
- **evaluator**：evaluate.py + src/ + data/（agent 看不到）。evaluate.py 透過 DataCatalog 讀取所有來源
- **watchdog**：背景跑 Validator + Factor-Level PBO

> **注意**：數據目錄已從 `data/market/` + `data/fundamental/` 遷移到按來源分離的 `data/yahoo/`, `data/finmind/`, `data/twse/`, `data/finlab/`。Docker volume mount 已在 Phase AI 更新。

## 啟動

```powershell
# 1. 啟動 3 容器
cd docker/autoresearch
docker compose up -d

# 2. 確認 evaluator 健康
docker exec autoresearch-agent curl -s http://evaluator:5000/health
# → {"status": "ok"}

# 3. 啟動研究循環
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
# 或 Host 模式（不用 Docker）：
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1 -Host
```

## 停止

```powershell
# Ctrl+C 停止 loop.ps1
# 容器繼續跑（evaluator + watchdog 常駐）

# 完全停止：
cd docker/autoresearch && docker compose down
```

## 檔案結構

```
docker/autoresearch/
├── work/
│   ├── factor.py          # agent 唯一可改的檔案
│   ├── results.tsv        # 實驗記錄（append-only）
│   └── .git/              # 獨立 git repo
├── watchdog_data/
│   ├── learnings.jsonl    # 結構化經驗
│   ├── factor_returns/    # PBO 用的每日報酬（L3+ 因子）
│   ├── factor_pbo.json    # Factor-Level PBO 結果
│   ├── library_health.json
│   ├── l5_query_count.json
│   └── baseline_ic_series.json
└── docker-compose.yml
```

## 評估管線

| Gate | 條件 | 說明 |
|------|------|------|
| L0 | ≤ 80 行 | 複雜度限制 |
| L1 | \|IC_20d\| ≥ 0.02 | 快篩（前 30 日） |
| L2 | \|ICIR_20d\| ≥ 0.30 | 固定 20d horizon（不做 best-of-N） |
| L3a | IC corr ≤ 0.50 | 去重（或 1.3× ICIR 替換） |
| L3b | ≥ 4 年正 IC | 穩定性 |
| L4 | Fitness ≥ 3.0 | WorldQuant 風格（含 turnover penalty） |
| L5 | OOS Thresholdout | 加 Laplace noise 保護 holdout |
| Stage 2 | 865+ 支 ICIR ≥ 0.20 | 防小樣本偏差 |

## 記憶 + 替換

- Agent 每次實驗前 `curl /learnings` 取得 forbidden 方向 + 成功模式 + 飽和度
- 同方向 ≥ 10 次 → evaluator 強制 L3 fail
- 新因子 ICIR ≥ 1.3× 舊因子 → 一對一替換（上限 10 次/週期）

## 監控

```bash
tail -5 docker/autoresearch/work/results.tsv           # 進度
cat docker/autoresearch/watchdog_data/factor_pbo.json   # PBO
cat docker/autoresearch/watchdog_data/library_health.json # 健康度
```
