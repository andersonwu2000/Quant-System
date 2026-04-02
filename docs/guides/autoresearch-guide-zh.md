# Autoresearch 操作指南

> 最後更新：2026-04-02（Phase AP）
> 權威操作手冊：`docs/autoresearch/RUNBOOK.md`

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
- **agent**：只有 work/（factor.py + results.tsv）+ data/（ro）。Git 操作限 allowlist（AP-12）
- **evaluator**：evaluate.py（唯一評估標準）+ src/（ro）。Credentials 為 ro（AP-13）
- **watchdog**：背景跑 Validator + Factor-Level PBO

**API 分離（AP-5）：**
- `/api/v1/factor-research/*` — 因子研究：start/stop、submit、status、history
- `/api/v1/auto-alpha/*` — 生產引擎：deployed、performance、start/stop deployed

## 啟動

### 方式一：API（推薦）

```powershell
# 1. 啟動 server
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000

# 2. 啟動容器
curl -X POST http://localhost:8000/api/v1/auto-alpha/start -H "X-API-KEY: dev-key"

# 3. 確認 evaluator 健康（AP-17：含數據可用性驗證）
curl http://evaluator:5000/health
# → {"status": "ok", "data_loaded": true, "cache_symbols": 200}

# 4. 啟動研究循環
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
```

### 方式二：手動 Docker

```powershell
cd docker/autoresearch
docker compose build    # 首次或代碼更新後
docker compose up -d
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
```

## 停止

```powershell
# Ctrl+C 停止 loop.ps1
cd docker/autoresearch && docker compose down
```

## 何時需要 rebuild

需要 `docker compose build`：
- `evaluate.py` / `eval_server.py` / `watchdog.py` 修改
- `Dockerfile.*` 修改
- Python 依賴變更

**不需要** rebuild（host mount 自動反映）：
- `src/` 代碼修改
- `data/` 數據更新
- `factor.py` 修改
- `docker-compose.yml` 修改（`docker compose up -d` 即可）

## 評估管線

| Gate | 條件 | 說明 |
|------|------|------|
| L0 | ≤ 80 行 | 複雜度限制 |
| L1 | \|IC_20d\| ≥ 0.02 | 快篩（慢 alpha 用 60d bypass） |
| L2 | \|ICIR\| ≥ 0.15（>0.50 觸發 ESS check） | AO-16：放寬下限，ICIR>0.50 需 ESS≥30 才放行 |
| L3a | IC dedup（Spearman） | AO-15：與 IC 計算方法一致 |
| L3b | ≥ 4 年正 IC | 穩定性 |
| L3c | Family budget ≤ 3 | AO-2：同家族 L4+ 上限 3 個 |
| L4a | Fitness ≥ 3.0 | WorldQuant 風格（含 turnover penalty） |
| L4b | ADV% ≤ 5% | AO-9：容量前移 |
| L5 | OOS Thresholdout | AP-21：動態 noise + session salt + hard budget |
| Stage 2 | 865+ 支 ICIR ≥ 0.20 | 防小樣本偏差（AP-15：_close_matrix 重建） |

**方法論改進（Phase AO+AP）：**
- Normalization 固定為 rank（AP-14：消除 5-variant 多重比較）
- 60d horizon 取樣間距改為 60d（AP-11：消除 overlap bias）
- OOS dates session-level 固定（AP-18：消除非確定性）
- Sharpe/Sortino 統一使用 risk_free_rate 2%（AO-14）
- Market correlation 門檻收緊至 0.65（AO-16）

## 安全設計

| 層面 | 機制 |
|------|------|
| Git | Allowlist：只允許 add/commit/tag/log/diff/status（AP-12） |
| Credentials | Read-only mount（AP-13） |
| Host 載入 | AST 分析 — 白名單 import + 禁止 dunder/eval/exec（AP-6） |
| Ensemble | 回傳 501（需 L3+L5 gate 整合後才重啟） |
| L5 budget | Hard block — 超過 200 次直接 FAIL（AP-C3） |
| evaluate.py | READ ONLY（OS permission + Docker COPY） |

## 資料契約

**唯一標準**：`evaluate.py`（scripts/autoresearch/evaluate.py）

**統一資料來源**：`FactorDataBundle`（`src/data/factor_data.py`，AP-1）
- PIT delay 從 registry 讀取（不硬編碼）
- 所有入口（evaluator / validator / strategy_builder / deployed_executor）共用

詳見：`docs/autoresearch/DATA_CONTRACT_INVENTORY.md`

## Family budget

commit message 必須標記 `[family: xxx]`：
```
git commit -m "experiment: revenue YoY growth [family: revenue]"
```

有效值：`revenue` / `value` / `quality` / `low_vol` / `momentum` / `event` / `other`

同家族 L4+ 因子上限 3 個。超過 → 自動降為 L3_family_budget。

## 監控

```bash
# 進度
tail -5 docker/autoresearch/work/results.tsv

# PBO + 因子健康度
cat docker/autoresearch/watchdog_data/factor_pbo.json
cat docker/autoresearch/watchdog_data/library_health.json

# 研究品質 KPI（AP-7）
python scripts/autoresearch/research_kpi.py

# Evaluator 健康
docker exec autoresearch-agent curl -s http://evaluator:5000/health

# OOS 日期配置
cat docker/autoresearch/watchdog_data/oos_config.json
```

## 相關文件

| 文件 | 用途 |
|------|------|
| `docs/autoresearch/RUNBOOK.md` | 權威操作手冊（< 200 行） |
| `docs/autoresearch/DATA_CONTRACT_INVENTORY.md` | 6 入口點資料契約 |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 實驗方法論標準 |
| `docs/plans/phase-ap-autoresearch-governance.md` | AP 計畫（25 項） |
| `scripts/autoresearch/program.md` | Agent 研究協議 |
