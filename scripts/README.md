# Scripts 分類

## Official — 系統運營用

| Script | 用途 |
|--------|------|
| `autostart.py` | Windows Task Scheduler 管理（PreMarket/Watchdog/Backup） |
| `daily_smoke_test.py` | 每日交易前 smoke test |
| `download_yahoo_price.py` | Yahoo 價格數據下載 |
| `download_finmind_data.py` | FinMind 基本面數據下載 |
| `download_finlab_data.py` | FinLab 數據下載 |
| `download_finlab_batch.py` | FinLab 批量下載 |
| `import_finlab_to_master.py` | 匯入 FinLab 到 SecuritiesMaster |
| `paper_trading_monitor.py` | Paper trading 監控（快照/日報/daemon） |
| `graduation_check.py` | 策略畢業檢查 |
| `silence_watchdog.py` | 暫時靜音 watchdog 告警 |
| `start.bat` | 啟動 backend + web |
| `_launch_*.bat` | Windows autostart 用啟動腳本 |

## Research — 因子研究與分析用

| Script | 用途 |
|--------|------|
| `autoresearch/` | Karpathy-style 自動因子研究（獨立子系統） |
| `run_strategy_backtest.py` | 單策略回測 |
| `run_validator_experiment25.py` | Experiment #25 跑 Validator |
| `run_factor_analysis.py` | 因子分析 |
| `run_full_factor_analysis.py` | 完整因子分析 |
| `run_fundamental_analysis.py` | 基本面分析 |
| `large_scale_factor_check.py` | 大規模 IC 驗證（865+ 支） |
| `large_scale_factor_analysis.py` | 大規模因子分析 |
| `run_stress_test.py` | 壓力測試 |
| `paper_vs_backtest.py` | Paper vs 回測比對 |
| `benchmark.py` | 效能基準測試 |

## Utility — 一次性或維護用

| Script | 用途 |
|--------|------|
| `migrate_data_dirs.py` | 數據目錄遷移（已完成） |
| `backfill_twse_institutional.py` | TWSE 法人數據回補 |
| `check_data_completeness.py` | 數據完整性檢查 |
| `cross_source_validate.py` | 跨數據源驗證 |

## Deprecated — 已被取代

| Script | 取代方式 |
|--------|---------|
| `run_factor_refinement.py` | 被 autoresearch 取代 |
| `run_factor_validation.py` | 被 Validator 取代 |
| `run_dual_factor_test.py` | 被 autoresearch 取代 |
| `run_dual_factor_validator.py` | 被 Validator 取代 |
| `run_alpha_pipeline_test.py` | 被整合測試取代 |
