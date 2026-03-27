# 假說生成指令（給 Claude Code 在另一個終端使用）

在另一個終端啟動 Claude Code，貼入以下指令：

```
讀取 data/research/memory.json 和 data/research/hypothesis_templates.json。

根據以下規則生成新的因子假說：

1. 看 memory.json 的 trajectories — 哪些因子通過了哪些階段、IC 值多少
2. 看 success_patterns — 什麼模式有效（revenue_acceleration ICIR 0.438 最強）
3. 看 forbidden_regions — 避開已知無效的模式
4. 看 hypothesis_templates.json — 哪些已存在、哪些已測試

生成 3-5 個新假說，寫入 hypothesis_templates.json。要求：
- 只用 revenue parquet 數據（不需要 financial_statement）
- 包含 40 天營收公布延遲
- 和現有因子差異化（不要是 revenue_acceleration 的簡單變體）
- 考慮學術文獻依據
- 每個假說需要 name, description, formula_sketch, academic_basis, data_requirements

寫完後告訴我新增了哪些假說。

完成後等 10 分鐘，再次讀取 memory.json 查看新結果，然後生成下一批假說。
持續這個循環。
```
