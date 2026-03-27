# Alpha Factor Autoresearch

Karpathy autoresearch 模式應用於量化因子研究。

## 架構

```
evaluate.py  (固定，不可改)   ←  IC/ICIR 計算 + 40 天延遲強制 + 複合評分
factor.py    (agent 唯一可改)  ←  因子定義：compute_factor(symbols, as_of, data)
program.md   (人類寫的協議)    ←  實驗循環指令
results.tsv  (實驗記錄)        ←  每次實驗追加一行
```

## 使用方式

```bash
# 1. 複製到獨立工作目錄
cp -r docs/reviews/autoresearch-alpha/ /path/to/workspace/
cd /path/to/workspace/

# 2. 開 Claude Code
claude

# 3. 初始 prompt
> 看 program.md，開始實驗
```

Agent 會自動進入循環：改 factor.py → 跑 evaluate.py → 記錄 results.tsv → 下一個。

## 安全設計

- **40 天營收延遲在 evaluate.py 強制**，不依賴 factor.py 的實作
- evaluate.py 是 READ ONLY — agent 不能修改評估標準
- 所有因子在相同條件下評估（同日期範圍、同 universe、同取樣頻率）

## 與原始 alpha_research_agent 的差異

| 項目 | alpha_research_agent | autoresearch-alpha |
|------|---------------------|-------------------|
| 假說生成 | 模板 + 網格（~150 個） | LLM 自由生成（無限） |
| 因子實作 | 名稱匹配代碼生成 | Agent 直接寫代碼 |
| 評估 | 5 層 + StrategyValidator | 固定 evaluate.py |
| 實驗追蹤 | memory.json | results.tsv + git |
| 持續性 | daemon 模式（會停） | Claude Code session |
