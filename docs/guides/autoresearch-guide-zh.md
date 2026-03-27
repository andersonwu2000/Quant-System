# 自動因子研究（Autoresearch）操作指南

## 概覽

自動因子研究系統會持續探索台股 alpha 因子。Claude Code agent 自動編寫因子 → 評估 → 記錄 → 重複，無需人工介入。通過嚴格驗證的因子會自動部署到 Paper Trading。

## 快速開始

### 前置條件

- Docker Desktop 已安裝並啟動
- Claude Code CLI 已安裝

### 首次設定（只需一次）

```powershell
cd D:\Finance
powershell -ExecutionPolicy Bypass -File docker/autoresearch/init.ps1
```

這會：建立工作區 → 建構 Docker image → 啟動容器 → 驗證健康。

### 啟動研究

```powershell
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop-docker.ps1
```

Agent 會自動開始跑實驗，session 結束後自動重啟。

### 停止研究

按 `Ctrl+C` 即可。容器會繼續待機（不佔資源），下次直接啟動 loop 就好。

### 完全關閉（含容器）

```powershell
# 先 Ctrl+C 停止 loop
cd D:\Finance\docker\autoresearch
docker compose down
```

## 日常操作

| 操作 | 指令 |
|------|------|
| 查看實驗進度 | `cat docker/autoresearch/work/results.tsv` |
| 查看狀態報告 | `powershell -File scripts/autoresearch/status.ps1` 然後開 `docs/research/autoresearch/status.md` |
| 查看 Watchdog 日誌 | `docker logs autoresearch-watchdog --tail 20` |
| 查看容器狀態 | `docker compose -f docker/autoresearch/docker-compose.yml ps` |
| 重啟容器 | `docker compose -f docker/autoresearch/docker-compose.yml restart` |
| 清除所有實驗重來 | `docker volume rm autoresearch_autoresearch-work` 然後重跑 init.ps1 |

## 因子通過流程

```
因子編寫 (agent)
  → L1-L4 in-sample 評估 (2017 ~ mid-2023)
    → L5 OOS holdout 驗證 (mid-2023 ~ 2024)
      → Stage 2 大規模 IC 驗證 (865+ 支股票)
        → StrategyValidator 15 項檢查
          → 通過 ≥14 項 + DSR ≥0.70
            → 自動部署 Paper Trading
            → 報告寫入 docs/research/auto/
```

## 查看成功因子

部署成功的因子會自動產生報告：

```
docs/research/autoresearch/
├── status.md                              ← 狀態報告（status.ps1 生成）
└── 20260328_143000_dual_sharpe_12_8.md    ← 部署報告（自動生成）
```

報告包含：指標、Validator 15 項結果、因子原始碼。

## 需要人工的唯一時機

**Paper Trading → Live Trading 的決定。** 建議觀察 3 個月後再決定。

## 安全機制

| 保護 | 說明 |
|------|------|
| 容器隔離 | evaluate.py 在 Docker 內跑，根檔案系統唯讀 |
| 無外網 | 容器只能存取本機 API server，無法連外部網路 |
| OOS 防過擬合 | L5 只回報 pass/fail，不洩漏 OOS 具體數值 |
| 複雜度限制 | factor.py 超過 60 行自動拒絕 |
| Watchdog | 監控停滯、crash、異常檔案、OOS 過擬合跡象 |
| 獨立 Git | agent 的 git reset 不影響主 repo |

## 更新 evaluate.py

修改 `scripts/autoresearch/evaluate.py` 後需重建容器：

```powershell
cd D:\Finance\docker\autoresearch
docker compose build
docker compose up -d
```

## 更新市場資料

更新 `data/` 目錄的 parquet 檔案後，自動生效（bind mount），不需重啟。

## 故障排除

| 問題 | 解法 |
|------|------|
| Agent 一直停 | 正常，loop.ps1 會自動重啟 |
| evaluate.py crash | 檢查 `docker/autoresearch/work/run.log` |
| Watchdog 報 STALE | Agent 可能卡住，Ctrl+C 重啟 loop |
| 容器啟動失敗 | `docker compose logs` 查看錯誤 |
| Docker Desktop 未啟動 | 開啟 Docker Desktop 後重試 |
