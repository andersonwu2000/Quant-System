# Phase F：自動化 Alpha 研究系統

> 完成日期：2026-03-26
> 狀態：✅ 完成
> 架構設計：`docs/architecture/AUTOMATED_ALPHA_ARCHITECTURE.md`

## 目標
將手動 Alpha 研究流程自動化為每日排程驅動的閉環系統。

## 產出（`src/alpha/auto/` — 12 檔案）

### F1 核心引擎
- `config.py`: AutoAlphaConfig + DecisionConfig + ResearchSnapshot + FactorScore + AlphaAlert
- `universe.py`: UniverseSelector — Scanner 動態候選 × 靜態約束 × 處置股排除
- `researcher.py`: AlphaResearcher — 包裝 AlphaPipeline + Regime 分類 + 因子評分
- `decision.py`: AlphaDecisionEngine — ICIR/Hit Rate 篩選 + REGIME_FACTOR_BIAS 調適 + DynamicFactorPool 整合
- `executor.py`: AlphaExecutor — weights→orders→risk→execution
- `scheduler.py`: AlphaScheduler — 8 個 cron job + `run_full_cycle()` + WS broadcasting

### F2 持久化 + 安全
- `store.py`: AlphaStore — JSON 持久化 (snapshots/alerts/performance, 365-entry cap)
- `alerts.py`: AlertManager — Regime 變化 / IC 反轉 / 因子退化偵測
- `safety.py`: SafetyChecker — 回撤熔斷 (5%) + 連續虧損暫停 (5 天)

### F3 API + 前端
- API: 10 端點 `/api/v1/auto-alpha/` (config/start/stop/status/history/performance/alerts/run-now + WS)
- Web: Auto-Alpha Dashboard (MetricCards + Regime + Factor 配置 + History + Alerts)
- WS: `auto-alpha` 頻道即時推送 pipeline 進度

### F4 Regime 引擎
- `factor_tracker.py`: 累計 IC + 回撤 + ICIR 排名 + trend 偵測
- `dynamic_pool.py`: Top-N 選擇 + 退化排除 + probation

## 每日流水線
```
08:50 Scanner → Universe (150 stocks - disposition)
08:52 AlphaPipeline.research() → 全因子 IC/ICIR/Regime
08:55 因子篩選 (ICIR>0.5) + DynamicFactorPool → Regime 調適 → 目標權重
09:00 風控檢查 → SinopacBroker 非阻塞下單
13:30 EOD 對帳 → 歸因 → 績效記錄 → 通知
```
