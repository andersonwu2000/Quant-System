# Documentation

## User-facing（使用者文件）

| File | Description |
|------|-------------|
| `user-guide-zh.md` | 使用指南（策略、CLI、因子庫） |
| `developer-guide-zh.md` | 開發指南（架構、模組、如何新增策略/因子） |
| `api-reference-zh.md` | API 端點參考 |

## Claude Code（AI 助手參考）

| File | When to read |
|------|-------------|
| `claude/ARCHITECTURE.md` | 修改代碼、新增模組時 |
| `claude/EXPERIMENT_STANDARDS.md` | 跑實驗、評估因子時 |
| `claude/SYSTEM_STATUS_REPORT.md` | 完成功能變更後更新 |

## Dev（開發內部文件）

```
dev/
├── PHASE_TRACKER.md          # 一頁式進度總覽（A~T）
├── DEVELOPMENT_LOG.md        # 開發日誌
├── APP_STABILITY_TESTING_REPORT.md
├── architecture/             # 架構設計文件
│   ├── ARCHITECTURE.md       # 完整系統架構
│   ├── AUTOMATED_ALPHA_ARCHITECTURE.md
│   ├── MULTI_ASSET_ARCHITECTURE.md
│   ├── WEB_ARCHITECTURE_V2.md
│   ├── WEB_DESIGN_SYSTEM.md
│   ├── ANDROID_APP_PLAN.md
│   └── REFACTORING_PLAN.md
├── evaluations/              # 技術評估
│   ├── BROKER_API_EVALUATION.md
│   ├── DATA_SOURCE_EVALUATION.md
│   └── PERSONAL_USE_GAP_REPORT.md
├── paper/                    # Paper Trading 日誌
├── plans/                    # Phase A~T 計畫書
│   └── phase-{a..t}-*.md
├── test/                     # 實驗報告
│   ├── RESEARCH_SUMMARY.md   # 研究總結
│   ├── realism_checklist.md  # 真實性檢查表
│   ├── 20260327_*.md         # 各次實驗
│   └── archive/              # 舊實驗（已被新版取代）
└── archive/                  # 封存文件
```

## Ref（參考文獻）

```
ref/
├── REFERENCES.md             # 文獻索引
├── books/                    # 教科書
├── papers/                   # 論文（alpha/backtesting/portfolio/data-modeling）
└── code-references/          # R/Python 套件文件
```
