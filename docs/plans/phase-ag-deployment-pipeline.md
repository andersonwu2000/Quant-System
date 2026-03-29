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

### 1.3 因子淘汰問題（Phase AB-4 C 提出）

部署後的因子可能退化（市場 regime 變化、alpha 衰減），但目前沒有移除機制。
baseline_ic_series.json 的因子只能被 1.3× 替換，不能主動移除。

**本 Phase 加入因子健康檢查**（Step 7）。

### 1.4 不在本 Phase 的範圍

- 多策略同時交易
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

### Step 7：因子健康檢查 + 淘汰機制

**位置**：`docker/autoresearch/watchdog.py` 新增 `_check_factor_health()`

部署後的因子可能退化。每月重新評估所有 active 因子：

```python
def _check_factor_health():
    """Monthly health check for deployed factors."""
    # 1. 對每個 active 因子重算 rolling 12 月 ICIR
    # 2. ICIR < 0.10 連續 3 個月 → probation
    # 3. probation 3 個月仍未恢復 → 自動移除
    # 4. 移除時：
    #    - 從 baseline_ic_series.json 刪除
    #    - 記錄到 learnings.jsonl（freed_direction）
    #    - 更新 library_health_metrics
    #    - 通知（寫報告到 docs/research/autoresearch/）
```

**觸發時機**：watchdog 主迴圈中，每月 1 日執行一次。

**淘汰門檻**：
| 狀態 | 條件 | 動作 |
|------|------|------|
| healthy | rolling 12m ICIR ≥ 0.10 | 保持 |
| probation | ICIR < 0.10 連續 3 個月 | 標記，不再用於 dedup 阻擋新因子 |
| retired | probation 3 個月未恢復 | 從 active 移除，記錄到 archived |

**和 Phase AF 替換的關係**：
- 替換 = 新因子更好 → 舊的被替代（主動）
- 淘汰 = 舊因子退化 → 自己被移除（被動）
- 兩者互補。替換不需要等退化，淘汰不需要等到有更好的

---

## 4. 網路架構修改

watchdog 需要呼叫 host API：

```yaml
# docker-compose.yml 修改（審批 #1 修正：獨立 deploy-net）
watchdog:
    networks:
      - deploy-net        # 只連 host API，不連 evaluator

networks:
  autoresearch-net:       # agent ↔ evaluator
  deploy-net:             # watchdog → host API
    internal: true
```

安全考量：watchdog 用獨立 `deploy-net`，只能存取 host API，不能存取 evaluator:5000。比加入 autoresearch-net 更安全。

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
| 7 | 因子健康檢查 + 淘汰 | ~50 行 |
| **總計** | | **~270 行** |

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

---

## 10. 嚴格審批（2026-03-29）

### 判定：架構方向正確，但有 3 個根本性問題。AG 不應在這些問題解決前啟動。

---

### 根本問題 1（CRITICAL）：整條管線沒有測過，預估工作量不可信

計畫列了 7 個 Step，預估 ~270 行。但：

- **PaperDeployer 是死代碼**（§3.2 自己承認）。沒人呼叫過 `deploy()`、`update_nav()`、`get_active()`。API 是否能跑不知道
- **DeployedStrategyExecutor 是全新模組**（~80 行）。依賴 PaperDeployer + StrategyBuilder + 數據管線。任何一個介面不對就卡住
- **watchdog → host API 的網路路徑從未打通**。`host.docker.internal` 在 Linux 不支援（需要 `extra_hosts`）
- **§6 驗證計畫**列了 5 個「確認 X」，但沒有具體的測試腳本或命令

**歷史教訓**（LESSONS #22）：18 個 Phase 標記完成，只有 1 個產出可驗證的結果。「代碼完成 ≠ 功能正常」。

**要求**：
1. 先驗證 PaperDeployer 的現有 API 能跑
2. 先在 host 上手動跑一次完整流程（手動提交因子 → 手動觸發 paper trade → 手動記錄 NAV）
3. 只有手動流程跑通後，才開始自動化（LESSONS #21：先手動 3 次再自動化）

### 根本問題 2（CRITICAL）：Validator 跑兩次有矛盾

§2 架構圖：
```
watchdog Validator (17 checks) → deployed=True
    ↓
factor-submit API → StrategyValidator.validate() (API 側再驗一次)
```

同一個因子驗兩次：
- 兩次的輸入數據可能不同（容器 vs host、universe 大小不同）
- 結果不同時信哪個？
- **每次各消耗一次 OOS query budget** — holdout 已降解，不該浪費

**要求**：明確兩次 Validator 的職責劃分（不同就寫清楚差異；相同就刪一個）。

### 根本問題 3（HIGH）：30 天 paper trading 沒有統計功效

22 個交易日的 Sharpe SE ≈ 0.21。兩個策略 Sharpe 差 0.3 需要 ~112 天才能區分。30 天只能抓「完全崩潰」的策略，無法比較「略好 vs 略差」。

FACTOR_PIPELINE_DEEP_REVIEW 已指出「OOS 1.5 年的 SE=0.82 都沒有檢定力」。30 天更差。

**要求**：
1. 30 天不叫「驗證」，叫「sanity check」
2. 替換主策略的決策標準需要 ≥ 90 天數據
3. 或明確定義 30 天後的決策邏輯（什麼情況繼續、什麼情況停止、什麼情況替換）

---

### 其他問題

| # | 問題 | 嚴重度 | 說明 |
|---|------|:------:|------|
| 4 | watchdog 開網路安全 | HIGH | 建獨立 deploy-net，不加入 autoresearch-net |
| 5 | 無重複提交防護 | MEDIUM | watchdog 重啟 → 重複提交 |
| 6 | PBO=0.0 前置條件不可信 | MEDIUM | 等 AB-4 修完 |
| 7 | 淘汰門檻 ICIR < 0.10 太寬 | MEDIUM | 至少 0.15（和 L2 一致），或用統計檢定 |
| 8 | 比較報告無決策標準 | LOW | 列了指標但沒定義怎麼決策 |
| 9 | 數據刷新依賴 | LOW | AD1 或手動更新 |

### 前置條件（嚴格版）

| 條件 | 狀態 | 性質 |
|------|:----:|:----:|
| AB-4 完成（PBO 修正） | ❌ | **BLOCKING** |
| PaperDeployer API 驗證能跑 | ❌ | **BLOCKING** |
| 手動端到端流程跑通 | ❌ | **BLOCKING** |
| 定義 paper trading 決策標準 | ❌ | **BLOCKING** |
| Validator 兩次驗證職責定義 | ❌ | **BLOCKING** |
| Phase AD1 數據刷新 | ❌ | 非 blocking 但影響 NAV |

**5 個 BLOCKING 條件。AG 的啟動時機是這 5 個全部解決之後，不是「Phase 2 研究完成」之後。**

## 11. 審批回覆（2026-03-29）— 獨立驗證

### 3 個根本問題：全部為真，全部接受

**#1 管線沒測過** — ✅ 正確。PaperDeployer 的 `update_nav()` / `get_active()` 從未被呼叫，`deploy()` 只在 `auto_alpha.py:829` 有一個呼叫點。`host.docker.internal` 在 Linux 不支援。

**接受要求**：先手動跑 3 次完整流程，再自動化。具體步驟：
1. 手動呼叫 `POST /auto-alpha/factor-submit` 提交一個已知因子
2. 手動觸發 paper trade（讀 deployed.json → 生成 weights → 記錄 NAV）
3. 確認 30 天後 auto-stop 觸發（可用 mock 時間加速）

**#2 Validator 跑兩次** — ✅ 正確。兩次用不同數據/universe，結果可能矛盾，且各消耗 L5 budget。

**修正**：刪除 API 側的 Validator。watchdog Validator 是唯一的驗證點（在 Docker 內，數據完整），通過後直接提交到 PaperDeployer（不再經過 factor-submit 的 Validator）。flow 簡化為：

```
watchdog Validator → deployed=True → 直接呼叫 PaperDeployer.deploy()
                                      （不走 factor-submit API 的 Validator）
```

factor-submit API 的 Validator 保留給**手動提交**使用（人工從外部提交的因子，不經過 watchdog）。

**#3 30 天統計功效** — ✅ 正確。22 個交易日的 Sharpe SE ≈ 3.39，完全沒有區分力。

**修正**：
- 30 天 = **sanity check**（只抓崩潰：累計虧損 > 10%、連續 5 天虧損）
- 替換主策略需要 **≥ 90 天**數據
- 明確決策邏輯：

| 30 天後 | 條件 | 動作 |
|---------|------|------|
| 崩潰 | 累計虧損 > 10% 或 MDD > 15% | 停止，標記失敗 |
| 正常 | 沒崩潰 | 延長到 90 天 |
| 90 天後優 | Sharpe 差 > 0.3 且 t-stat > 1.5 | 人工決定是否替換 |
| 90 天後平 | 差距不顯著 | 繼續觀察或保持原策略 |
| 90 天後劣 | Sharpe 差 < -0.3 | 停止 |

### 其他問題

| # | 回覆 |
|---|------|
| 4 | ✅ 接受 deploy-net（已修改 §4） |
| 5 | ✅ 接受 submitted_factors.json 去重 |
| 6 | ✅ 接受 AB-4 為 BLOCKING 前置 |
| 7 | **修正**：淘汰門檻從 0.10 改為 0.15。理由同意 — 和 L2 舊門檻一致，且「已部署因子退化到 0.15 以下」確實該 probation |
| 8 | ✅ 接受。比較報告需定義決策標準（已在 #3 修正中定義） |
| 9 | ✅ 接受。月頻可手動更新 |

### 修正後的前置條件

| 條件 | 狀態 | 性質 |
|------|:----:|:----:|
| AB-4 完成（PBO 修正） | ❌ | **BLOCKING** |
| PaperDeployer API 驗證能跑 | ❌ | **BLOCKING** |
| 手動端到端流程跑通 3 次 | ❌ | **BLOCKING** |
| 定義 paper trading 決策標準 | ✅ 已在 §11 定義 | 已解決 |
| Validator 職責定義 | ✅ watchdog 唯一驗證 | 已解決 |
| Phase AD1 數據刷新 | ❌ | 非 blocking |

**3 個 BLOCKING → AG 啟動前必須完成 AB-4 + PaperDeployer 驗證 + 手動流程跑通。**
