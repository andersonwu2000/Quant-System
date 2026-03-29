# Phase AG：因子部署管線

> 前置：Phase 2（研究週期完成，累積足夠因子 + PBO 穩定）
> 目標：打通 autoresearch 發現 → Validator 驗證 → paper trading 部署 → 監控 的完整路徑
> 來源：管線架構審計（2026-03-29）發現的 8 個結構性斷點

---

## 1. 問題

### 1.1 現狀：兩個斷開的系統

```
Trading Pipeline (execute_pipeline)                Research Pipeline (autoresearch)
  cron → config.active_strategy → on_bar → 下單      agent → evaluate → L1-L5 → watchdog → 報告
  ↑ 完全靠 config 硬編碼                              ↑ 發現因子後停在報告，沒有路徑通往交易
```

中間沒有橋。研究發現的因子無法自動或半自動地進入 paper trading。

### 1.2 關鍵斷點

| # | 斷點 | 影響 |
|---|------|------|
| 1 | autoresearch 因子 → 交易：無路徑 | 發現的因子只能手動複製 |
| 2 | PaperDeployer 是死代碼 | deploy() 後沒有 executor |
| 3 | Trading + Auto-Alpha 共享 Portfolio 無隔離 | race condition |
| 4 | AlphaScheduler cron 定義了但未註冊 | 自動化不存在 |

### 1.3 不在本 Phase 的範圍

- 多策略同時交易（Phase 4）
- 14 種組合最佳化接入（Phase AA-2）
- 成本感知建構（Phase AA-2）
- Live trading（需要券商 API 穩定後）

---

## 2. 目標架構

```
autoresearch agent
  ↓ L5 通過
watchdog Validator (17 checks)
  ↓ 10 項 HARD 全過 → deployed=True
  ↓ 寫報告到 docs/research/autoresearch/
  ↓
[NEW] watchdog 自動呼叫 factor-submit API
  ↓
strategy_builder.build_from_research_factor()
  ↓ 包裝成 ResearchFactorStrategy
  ↓
StrategyValidator.validate() (API 側再驗一次)
  ↓
PaperDeployer.deploy()
  ↓ 存 deployed.json
  ↓
[NEW] DeployedStrategyExecutor (背景 job)
  ↓ 每月讀 deployed.json → generate weights → 下單
  ↓ 獨立 NAV 追蹤（不混入主 Portfolio）
  ↓
[NEW] 30 天監控 → 和 revenue_momentum_hedged 比較
  ↓
Phase 3 結束：人工決定是否替換主策略
```

---

## 3. 實施步驟

### Step 1：watchdog 自動提交部署因子

**位置**：`docker/autoresearch/watchdog.py` 的 `_process_pending()`

當 `deployed=True` 時，watchdog 透過 evaluator 網路呼叫 host API 提交因子：

```python
if validator_report and validator_report.get("deployed"):
    # 現有：寫報告
    _write_background_report(results, validator_report, factor_code)
    # 新增：自動提交到 API
    _auto_submit_factor(factor_code, results, validator_report)
```

```python
def _auto_submit_factor(factor_code, results, validator_report):
    """Submit deployed factor to host API for paper trading."""
    import urllib.request
    payload = json.dumps({
        "name": f"auto_{time.strftime('%Y%m%d_%H%M%S')}",
        "code": factor_code,
        "direction": 1,
        "top_n": 15,
        "source": "autoresearch",
        "validator_report": validator_report,
    }).encode()
    try:
        req = urllib.request.Request(
            "http://host.docker.internal:8000/auto-alpha/factor-submit",
            data=payload, headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        log(f"Factor submitted: {resp.read().decode()}")
    except Exception as e:
        log(f"Factor submit failed: {e}")
```

**注意**：watchdog 目前 `network_mode: none`，需要改為加入 autoresearch-net 或另建網路。

### Step 2：修復 PaperDeployer

**位置**：`src/alpha/auto/paper_deployer.py`

現有問題：
- deploy() 存 JSON 但沒有 executor
- update_nav() 存在但沒人呼叫
- 沒有和 revenue_momentum_hedged 的比較機制

修復：
- 確認 deploy/stop/get_active 邏輯正確
- 加入 `get_factor_code()` 方法（從存儲讀取因子原始碼）
- 加入 `compare_with_benchmark()` 方法

### Step 3：建立 DeployedStrategyExecutor

**位置**：新增 `src/alpha/auto/deployed_executor.py`

```python
class DeployedStrategyExecutor:
    """執行已部署的自動因子策略。獨立 NAV 追蹤。"""

    def __init__(self, deployer: PaperDeployer, config: TradingConfig):
        self.deployer = deployer
        self.config = config

    async def execute_all(self):
        """對每個 active 部署策略生成權重並記錄（不實際下單）。"""
        for strategy in self.deployer.get_active():
            weights = self._generate_weights(strategy)
            self._record_paper_trade(strategy, weights)
            self.deployer.update_nav(strategy.name, self._calculate_nav(strategy, weights))

    def _generate_weights(self, strategy):
        """用 ResearchFactorStrategy 生成目標權重。"""
        ...

    def _record_paper_trade(self, strategy, weights):
        """記錄模擬交易到 data/paper_trading/auto/{name}/"""
        ...
```

**關鍵設計決策**：
- **不實際下單** — 只記錄模擬結果。避免和主策略衝突
- **獨立 NAV** — 每個部署因子有自己的 NAV 追蹤
- **月頻執行** — 和因子策略的換倉頻率一致

### Step 4：註冊背景 Job

**位置**：`src/scheduler/__init__.py`

```python
# Phase 3: 部署因子月度模擬執行
if config.auto_alpha_enabled:
    self._scheduler.add_job(
        self._run_deployed_strategies,
        trigger=CronTrigger.from_crontab("0 10 12 * *"),  # 每月 12 日 10:00
        id="deployed_strategies",
    )
```

### Step 5：比較報告

**位置**：新增 `src/alpha/auto/comparison.py`

每月比較已部署因子 vs revenue_momentum_hedged：

```python
def generate_comparison_report(deployed_navs, benchmark_nav):
    """
    比較指標：
    - Sharpe ratio（兩者）
    - Cumulative return（兩者）
    - Max drawdown
    - Correlation
    - 結論：部署因子是否優於基準
    """
```

報告寫到 `docs/research/autoresearch/comparison/`。

### Step 6：30 天自動停止 + 人工決策

- PaperDeployer 現有 30 天 auto-stop ✓
- 停止時生成最終比較報告
- 人工決定是否：
  - 更新 `config.active_strategy` 切換主策略
  - 繼續 paper trading 延長觀察
  - 放棄

---

## 4. 網路架構修改

watchdog 需要呼叫 host API：

```yaml
# docker-compose.yml 修改
watchdog:
    # network_mode: none  ← 移除
    networks:
      - autoresearch-net  # 加入網路
```

安全考量：watchdog 只需要存取 host API（factor-submit），不需要外網。可以用 internal network。

---

## 5. 不做的事

| 提議 | 為什麼不做 |
|------|-----------|
| 自動替換主策略 | 太危險。30 天 paper trading 後人工決定 |
| 多因子同時交易 | Phase 4 的範圍。先一個一個驗證 |
| 接入 14 種組合最佳化 | Phase AA-2。先用 signal_weight 驗證因子本身 |
| Live trading | 需要 SinopacBroker 穩定。先 paper |
| 即時切換 | 月頻策略不需要即時切換 |

---

## 6. 驗證

1. 手動提交一個已知好的因子（如 momentum_12_1），確認全流程通
2. 確認 PaperDeployer 正確記錄 NAV
3. 確認 30 天後 auto-stop 觸發
4. 確認比較報告格式正確
5. 確認 watchdog 自動提交不會重複提交同一因子

---

## 7. 前置條件

| 條件 | 狀態 | 說明 |
|------|:----:|------|
| Phase 2 研究完成 | ⏳ | 累積 3+ 個 L5 通過因子 |
| PBO 穩定 | ✅ | 0.0 (n_independent=26) |
| Validator 17 checks 正常 | ✅ | watchdog 已跑通 |
| execute_pipeline 統一管線 | ✅ | Phase S 完成 |
| 因子替換機制 | ✅ | Phase AF 完成 |

---

## 8. 預估

| Step | 內容 | 工作量 |
|------|------|:------:|
| 1 | watchdog 自動提交 | ~30 行 |
| 2 | PaperDeployer 修復 | ~20 行 |
| 3 | DeployedStrategyExecutor | ~80 行 |
| 4 | Scheduler 註冊 | ~10 行 |
| 5 | 比較報告 | ~60 行 |
| 6 | 30 天停止 + 報告 | ~20 行 |
| **總計** | | **~220 行** |

---

## 9. 開發路線圖（全系統）

Phase AG 在整體架構中的位置：

```
已完成
  Phase A-I     基礎建設 + 因子庫 + 跨資產 + Live 代碼
  Phase K-M     數據品質 + 策略轉型 + 下行保護
  Phase S       統一交易管線
  Phase U/Y     Autoresearch 模式 + 容器化
  Phase AB/AC   Factor-Level PBO + Validator 方法論凍結
  Phase AE/AF   Docker 隔離 + 記憶/替換機制

進行中
  Phase 2       乾淨研究週期（autoresearch 跑實驗）
    │
    ▼
第一優先 → Phase AG（本計畫）
    │  打通 autoresearch → paper trading
    │  不做這個，研究成果無法驗證
    │
    ▼
第二優先 → Phase AA-2（組合最佳化接入）
    │  signal_weight → inverse-vol / cost-aware construction
    │  改善 paper trading 實際表現
    │  但可先用簡單權重驗證因子本身
    │
    ▼
第三優先 → Phase N + CA 憑證（Live Trading）
    │  需外部條件（永豐 CA 憑證）
    │  Paper trading 驗證成功後才有意義
    │
    ├── Phase AD（數據管線自動化）     ← 可並行
    │   營收/籌碼定時更新，trading pipeline 依賴
    │
    └── Phase R 收尾（R7-R9）         ← 可並行
        代碼衛生（文件清理、型別、測試覆蓋）

延後（有了更好但不阻塞）
  Phase J       跨資產自動化（等台股因子穩定）
  Phase N2      Web 前端 Alpha Research 頁面
  Phase Z3      引擎加速（效能已可接受）
  Phase E       Live Trading 生產測試（等 CA 憑證）
```

### 核心邏輯

**研究 → 部署 → 最佳化 → 上線。** 每一步都在前一步驗證成功後才有意義：

| 階段 | 驗證什麼 | 失敗則 |
|------|---------|--------|
| Phase 2（研究） | 因子在 IS+OOS 有信號 | 繼續探索新方向 |
| Phase AG（部署） | 因子在 paper trading 可交易 | 調整策略建構或換因子 |
| Phase AA-2（最佳化） | 最佳化改善 net return | 保持簡單權重 |
| Phase N（上線） | Live 和 paper 一致 | 排查執行落差 |

### 已廢棄計畫

| 計畫 | 被什麼取代 |
|------|-----------|
| Phase P（Auto Research） | Phase U（autoresearch 模式） |
| Phase Q（Strategy Refinement） | Phase AA + AC |
| Phase X（Anti-Overfitting） | Phase AC（Validator 方法論凍結） |
