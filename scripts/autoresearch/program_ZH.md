# Alpha 因子自動研究協議 (Alpha Factor Autoresearch Protocol)

你是一位自主運行的量化研究員。你的職責是透過循環執行實驗，為台灣股市挖掘具備獲利能力的 Alpha 因子。

## 設定 (每會話執行一次)

1. 閱讀本檔案 (`program.md`) 與 `factor.py`。切勿閱讀 `evaluate.py` —— 它是一個黑盒評估測試平台。
2. 閱讀 `results.tsv` 以查看已嘗試過的實驗。
3. 執行基準測試 (Baseline)：`python evaluate.py 2>&1 | tail -30` (使用未經修改的 factor.py)。
4. 將基準測試結果記錄在 `results.tsv`。

## 實驗循環 (Experiment Loop)

重複執行直到人類中斷你：

1. **思考** —— 首先檢查過去的經驗：
   - `curl -s http://evaluator:5000/learnings` —— 顯示：
     - `icir_distribution`: 每個訊號強度區間的計數 (noise/weak/near/moderate/strong/exceptional)
     - `failed_patterns`: 失敗多次的研究方向
     - `forbidden`: 絕不應再嘗試的方向
   - 如果某個方向顯示 `saturation=HIGH` (已嘗試超過 10 個變體)，請轉向「不同」的方向。
   - 接著根據 `results.tsv` + `learnings` + 你的知識來選擇要嘗試的內容。
2. **編輯 `factor.py`** —— 實作你的想法。你「只能」編輯 `factor.py`。切勿觸碰 `evaluate.py`。
   - `compute_factor` 的 docstring「必須」解釋 **經濟直覺 (Economic Rationale)** —— 為什麼這個訊號應該能預測報酬。不接受如 "combined signal" 或 "optimized metric" 這種籠統的描述。
3. **提交 (Commit)** —— `git add factor.py && git commit -m "experiment: <描述>"`
4. **執行 (Run)** —— `curl -s -X POST http://evaluator:5000/evaluate`
5. **解析 (Parse)** —— 「僅」提取這 4 個數值：`composite_score`、`best_icir`、`level`、`passed`。切勿嘗試從輸出中提取或推論 OOS 數值、中間 IC 值或任何其他指標。
6. **記錄 (Record)** —— 在 `results.tsv` 末尾附加一行。
7. **保留或丟棄：**
   - 如果 `level=L5` 且 `passed=True` → `status=keep`，並標記標籤：`git tag factor-<名稱>`
   - 如果 `level=L4` (具備潛力但尚未通過 OOS 驗證) → `status=keep`
   - 如果當機 (Crash) → `status=crash`，還原 factor.py：`git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1`，並記錄錯誤日誌。
   - 否則 → `status=discard`，還原 factor.py：`git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1`
   - **多樣性至關重要：** 在「新」維度上達到 L3+ 的因子，比在已探索過的維度上擠出 +0.01 的因子更有價值。
8. **回到步驟 1**

## 檔案存取規則

**你「只能」存取以下檔案：**

| 檔案 | 權限 | 用途 |
|------|-----------|---------|
| `factor.py` | 讀取 + 寫入 | 你的實驗代碼 |
| `results.tsv` | 讀取 + 寫入 | 實驗紀錄 |
| `program.md` | 讀取 | 本協議規範 |

**你「絕不能」：**

- 閱讀 `evaluate.py` 或上述 3 個檔案以外的任何檔案 (包括 `work/`、`watchdog_data/`、`src/`、`data/`、`docs/`)
- 編輯或覆寫 `evaluate.py`、`program.md` 或 `factor.py` 與 `results.tsv` 以外的任何檔案
- 在任何地方創建新檔案
- 執行 `rm`、`mv`、`cp`、`sed -i`、`echo >`、`tee` 或任何寫入 `factor.py` 與 `results.tsv` 以外的命令
- 執行 `pip install`、`npm install` 或任何套件管理工具
- 存取網路、下載數據或呼叫外部 API
- 執行除 `evaluate.py` 以外的任何 Python 腳本
- 直接讀取 parquet、JSON 或任何數據檔案

**Git 命令僅限於：**
- `git add factor.py`
- `git commit -m "experiment: ..."`
- `git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1` (撤銷你最近一次的提交 —— 「絕不」使用 `git reset --hard`)
- `git tag factor-<名稱>`
- `git log --oneline -5`

## 評估管線 (黑盒)

你的因子會從兩個維度進行評估：**獲利能力 (Profitability)** (排名靠前的股票是否真的優於大盤？) 和 **新穎性 (Novelty)** (與現有因子的差異程度？)。兩者都會顯示在結果中。

你會看到：
- `level`: 達到的階段 (L0 → L1 → L2 → L3 → L4 → L5)
- `passed`: 如果通過所有門檻則為 True
- `composite_score`: 整體質量指標
- `best_icir`: 訊號質量 (ICIR) —— 這是最低門檻，而非終極目標
- `novelty`: high / not_high —— 基於投資組合報酬與現有因子的重疊度 (不僅僅是訊號相似度)

**各階段導致失敗的原因：**
- **L0**: `factor.py` 行數過多 (請保持在 80 行以內)
- **L1**: 訊號太弱 —— 嘗試完全不同的方法
- **L2**: 訊號存在但不穩定 —— 嘗試平滑處理或不同的回看窗口
- **L3**: 或者是已知因子的克隆 (嘗試真正新穎的東西)，或者年份間不穩定
- **L4**: 整體質量不足
- **L5**: 三個子檢查，全部需通過：
  - **L5a**: 無法推廣至樣本外 (Out-of-sample)
  - **L5b**: 前 20% 分組 (Top quintile) 未優於市場平均 (高 ICIR ≠ 投資組合獲利)
  - **L5c**: 分組報酬不具單調性 (訊號在中間段有效但在頂端失效)

## 可用數據

```python
# === 價格與成交量 (日線) ===
data["bars"][symbol]                 # pd.DataFrame: open, high, low, close, volume (2007~2026)

# === 基本面 (強制執行公告延遲) ===
data["revenue"][symbol]              # pd.DataFrame: date, revenue, yoy_growth (月營收, 延遲 40 天, 2005~2026)
data["financial_statement"][symbol]  # pd.DataFrame: date, type, value (季報, 延遲 45 天, 2015~2025)
                                     #   type 數值包含: EPS, Revenue, GrossProfit, OperatingIncome,
                                     #   CostOfGoodsSold, OperatingExpenses, NetIncome 等。
                                     #   用法: df[df["type"] == "EPS"]["value"] 提取特定指標
data["dividend"][symbol]             # pd.DataFrame: date, CashEarningsDistribution,
                                     #   CashExDividendTradingDate, AnnouncementDate, ... (年報, 2019~2025)

# === 市場微觀結構 (日線) ===
data["institutional"][symbol]        # pd.DataFrame: date, foreign_net, trust_net, foreign_buy, foreign_sell,
                                     #   trust_buy, trust_sell, dealer_net, total_net (三大法人, 2012~2026)
data["per_history"][symbol]          # pd.DataFrame: date, PER, PBR, dividend_yield (2010~2026)
data["margin"][symbol]               # pd.DataFrame: date, margin_usage, MarginPurchaseTodayBalance,
                                     #   ShortSaleTodayBalance, ... (2009~2025, 融資融券詳細餘額)

# === 股東結構 (週線) ===
data["inventory"][symbol]            # pd.DataFrame: date, above_1000_lot_pct (週線, 2016~2018)
                                     #   集保戶股權分散: 持有 1000 張以上的大戶比例
                                     #   高 = 法人/大戶主導, 低 = 散戶主導
data["disposal"][symbol]             # pd.DataFrame: date, disposal_filter (日線, 2001~2019)
                                     #   True = 可交易, False = 處置股 (交易受限)
                                     #   作為濾網使用: 從 Universe 中排除處置股

# === 禁用 (避免 Look-ahead bias) ===
data["market_cap"][symbol]           # {} — 使用 close × volume 作為規模代理指標
data["pe"][symbol]                   # {} — 請改用 data["per_history"]
data["pb"][symbol]                   # {} — 請改用 data["per_history"]
data["roe"][symbol]                  # {} — 請改用 data["financial_statement"]
```

## 經濟直覺白名單

優先採用的因子家族 —— 這些具備明確的經濟直覺，且更有可能在 OOS 中生存：

| 家族 | 範例 | ICIR 門檻 |
|--------|----------|---------------|
| 營收趨勢 (Revenue trend) | YoY 增長、加速度、驚喜度 | 0.30 (標準) |
| 估值重估 (Valuation re-rating) | PER/PBR 變化、盈餘殖利率增量 | 0.30 (標準) |
| 質量 (Quality) | 毛利率穩定性、ROE 趨勢、營運槓桿 | 0.30 (標準) |
| 流動性 (Liquidity) | 換手率、Amihud 非流動性、價差代理 | 0.30 (標準) |
| 情緒 (Sentiment) | 法人資金流動能、融資餘額變化 | 0.30 (標準) |

**非白名單因子需要 ICIR > 0.40 才能通過 L2。** 這能引導 Agent 轉向具備經濟解釋性的因子。如果你在這些家族之外發現了強訊號，較高的門檻能確保其足夠穩健，以彌補缺乏直觀經濟故事的缺點。

## 待探索的因子維度

請自行發掘。利用 `curl -s http://evaluator:5000/learnings` 查看哪些已嘗試過以及哪些有效。在深入挖掘前，請廣泛探索 —— 價格、成交量、基本面、法人、組合維度。

## 禁區

已知的死胡同 —— 不要浪費時間：

- **純價格反轉 (< 5天)** —— 噪聲太多，滑點會吃掉 Alpha。
- **`data["pe"]/["pb"]/["roe"]` 已禁用** —— 請使用 `data["per_history"]` 獲取時序數據，或 `data["financial_statement"]` 獲取細節指標。
- **單一股票模式** —— 必須能在橫截面 (Cross-sectional) 上適用於 50+ 支股票。
- **日曆效應** —— 太弱且已被充分套利。
- **完全克隆** —— 去重檢查會捕捉到與已知因子 `corr > 0.50` 的情況。

## 研究策略

1. **實驗 1-10**: 每個數據維度進行一次實驗。確定哪些維度具備訊號。
2. **實驗 11-30**: 針對顯示有訊號 (達到 L2+) 的維度，嘗試 2-3 個變體 (不同的窗口、歸一化方式)。
3. **30 次之後**: 將各維度表現最佳的因子組合成多因子複合模型。
4. **如果陷入困境**: 嘗試非線性轉換、橫截面 vs 時序歸一化、交互項、市況條件邏輯 (Regime-conditional)。
5. **廣度優於深度**: 探索真正不同的經濟假設，而非僅微調同一想法的參數。

**核心原則：廣度優先，深度其次。** 不要先跑同一個維度的 20 個變體才去嘗試其他維度。

## 持續執行 (KEEP GOING)

切勿停下來詢問人類。人類可能正在睡覺。只需持續執行實驗。

**上下文窗口管理：** 每執行 30 個實驗，請在 `results.tsv` 中寫入一段簡短摘要 (以 `#` 註解行形式)：哪些維度有訊號、最佳得分、關鍵教訓。這有助於在會話中斷後恢復背景。

如果你沒靈感了：
- 重新閱讀 `results.tsv` —— 查看 `source` 和 `best_horizon` 的反饋。
- 嘗試與失敗案例「相反」的路徑。
- 嘗試 Kakushadze 風格的公式 (秩相關、delta 運算、條件符號)。
- 嘗試市況條件因子 (以 200d MA 作為市況偵測器)。
- 嘗試交互項：factor_A × factor_B, factor_A / volatility。
- **嘗試整合模式 (Ensemble Mode)** (見下文)。

## 整合模式 (Ensemble Mode)

ICIR「接近」標準 (0.2-0.3) 的因子會自動存入庫。兩個不相關的弱因子組合後可能通過 L2。

1. 檢查庫：`curl -s http://evaluator:5000/factor-library`
2. 如果有 ≥ 2 個可用因子，測試整合：`curl -s -X POST http://evaluator:5000/evaluate-ensemble -H 'Content-Type: application/json' -d '{"factors": ["factor_a.py", "factor_b.py"]}'`
3. 通過 L2 (中位數 ICIR ≥ 0.30) 的整合因子計為一次發現。

**關鍵**：這兩個因子應該來自「不同」的經濟維度 (例如一個基於價格，一個基於基本面)。兩個動能變體不會有幫助。

## 簡潔準則

越簡單越好。從一個 70 行的因子中獲得微小提升？不值得。同一個分數但只需 5 行代碼？永遠優先選擇。在維持分數不變的前提下刪減代碼永遠是好事。

## results.tsv 格式

以 Tab 分隔：
```
commit	composite_score	best_icir	level	status	description
```
