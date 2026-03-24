/**
 * Financial glossary for contextual help tooltips.
 * Each entry has bilingual (en/zh) definitions.
 */
export interface GlossaryEntry {
  en: string;
  zh: string;
}

export const glossary: Record<string, GlossaryEntry> = {
  // ── Alpha Research ──
  ic_mean: {
    en: "Information Coefficient (IC) measures the correlation between predicted factor values and actual forward returns. Ranges from -1 to +1; values above 0.03 are generally considered meaningful.",
    zh: "信息係數 (IC) 衡量因子預測值與實際未來收益之間的相關性。範圍 -1 到 +1，通常 IC 超過 0.03 即具有參考價值。",
  },
  icir: {
    en: "IC Information Ratio = IC Mean / IC Std. Measures the consistency of a factor's predictive power. ICIR above 0.5 indicates a stable and reliable signal.",
    zh: "IC 信息比率 = IC 均值 / IC 標準差。衡量因子預測能力的穩定性，ICIR 超過 0.5 表示信號穩定可靠。",
  },
  hit_rate: {
    en: "The percentage of periods where the factor's IC is positive. A hit rate above 50% means the factor predicts the correct direction more often than not.",
    zh: "因子 IC 為正值的時期佔比。命中率超過 50% 表示因子多數時間能預測正確方向。",
  },
  ls_sharpe: {
    en: "Long/Short Sharpe Ratio: the risk-adjusted return of a strategy that goes long the top quantile and short the bottom quantile of stocks ranked by the factor.",
    zh: "多空 Sharpe 比率：按因子排序，做多頂分位、做空底分位的策略風險調整收益。數值越高，因子的多空分層效果越好。",
  },
  monotonicity: {
    en: "Measures whether quantile returns increase (or decrease) smoothly from bottom to top. A perfectly monotonic factor has value 1.0, meaning each quantile earns progressively more.",
    zh: "衡量分位數收益是否從低到高平滑遞增（或遞減）。完全單調的因子為 1.0，表示每個分位的收益依序遞增。",
  },
  turnover: {
    en: "The fraction of portfolio holdings that change each rebalance period. High turnover incurs more transaction costs; the breakeven cost shows the maximum tolerable cost per trade.",
    zh: "每次再平衡時持倉變動的比例。換手率越高，交易成本越大；盈虧平衡成本表示每筆交易能承受的最大成本。",
  },
  cost_drag: {
    en: "Annualized transaction cost drag in basis points. Estimated as: average turnover × assumed cost per trade × annualization factor. Deducted from gross alpha to get net alpha.",
    zh: "年化交易成本侵蝕（基點）。計算方式：平均換手率 × 假設每筆交易成本 × 年化係數。從毛 Alpha 中扣除得到淨 Alpha。",
  },
  breakeven_cost: {
    en: "The maximum single-trip transaction cost (in bps) at which the factor's long-short spread still generates positive returns. If your actual cost exceeds this, the factor is unprofitable.",
    zh: "使因子多空價差收益仍為正的最大單邊交易成本（基點）。若實際成本超過此值，該因子不具獲利能力。",
  },
  neutralization: {
    en: "Cross-sectional neutralization removes unwanted common exposures (market, industry, or size) from factor scores, isolating the pure stock-specific signal.",
    zh: "橫截面中性化：從因子分數中移除不需要的共同曝險（市場、行業或規模），以提取純粹的個股信號。",
  },
  quantile_returns: {
    en: "Stocks are sorted by factor score into N equal groups (quantiles). The average return of each group shows whether the factor discriminates between winners and losers.",
    zh: "將股票按因子分數排序分為 N 等份（分位數），計算每組的平均收益，以觀察因子能否有效區分強弱股。",
  },
  composite_alpha: {
    en: "A combined signal created by blending multiple individual factor scores (after standardization and optional orthogonalization). Diversifies across signal sources for more robust alpha.",
    zh: "將多個單因子分數（經標準化及可選正交化後）混合而成的合成信號。跨信號源分散化可提高 Alpha 的穩健性。",
  },
  factor: {
    en: "A quantitative characteristic (e.g., momentum, value, volatility) computed for each stock that is hypothesized to predict future returns. Factors are the building blocks of alpha research.",
    zh: "為每檔股票計算的量化特徵（如動量、價值、波動率），假設其能預測未來收益。因子是 Alpha 研究的基本構件。",
  },

  // ── Factors ──
  momentum: {
    en: "Past 12-month return (excluding the most recent month). Stocks that have performed well tend to continue outperforming in the near term (trend continuation).",
    zh: "過去 12 個月報酬（排除最近 1 個月）。過去表現優異的股票傾向在短期內持續領先（趨勢延續效應）。",
  },
  mean_reversion: {
    en: "Measures how far a stock's price has deviated below its moving average (Z-score). Expects oversold stocks to revert to their mean — a contrarian signal.",
    zh: "衡量股價偏離移動平均線下方的程度（Z-score）。預期超賣股票會回歸均值 — 逆勢信號。",
  },
  volatility: {
    en: "Historical price volatility (standard deviation of returns). Low-volatility stocks have historically delivered better risk-adjusted returns (low-vol anomaly).",
    zh: "歷史價格波動率（報酬的標準差）。低波動率股票在歷史上往往能提供更佳的風險調整收益（低波動異常現象）。",
  },
  rsi: {
    en: "Relative Strength Index: oscillator ranging 0-100. Below 30 = oversold (buy signal), above 70 = overbought. Signal strength = 100 - RSI.",
    zh: "相對強弱指數：振盪指標，範圍 0-100。低於 30 為超賣（買入信號），高於 70 為超買。信號強度 = 100 - RSI。",
  },
  ma_cross: {
    en: "Moving Average Crossover: goes long when the fast MA (e.g., 10-day) crosses above the slow MA (e.g., 50-day). Signal strength depends on crossover magnitude.",
    zh: "均線交叉：當快均線（如 10 日）上穿慢均線（如 50 日）時做多。信號強度取決於交叉幅度。",
  },
  vpt: {
    en: "Volume-Price Trend: combines price change and volume to detect accumulation (buying pressure) or distribution (selling pressure).",
    zh: "量價趨勢：結合價格變動與成交量，偵測吸納（買入壓力）或派發（賣出壓力）信號。",
  },
  reversal: {
    en: "Short-term reversal: stocks with recent extreme losses tend to bounce back. The opposite of momentum — works best at very short horizons (1-4 weeks).",
    zh: "短期反轉：近期極端下跌的股票傾向反彈。與動量相反 — 在極短週期（1-4 週）效果最佳。",
  },
  illiquidity: {
    en: "Amihud illiquidity ratio: absolute return / trading volume. Illiquid stocks carry a premium because investors demand compensation for higher transaction costs.",
    zh: "Amihud 流動性不足比率：|報酬| / 成交量。低流動性股票因交易成本較高，投資人要求流動性溢價。",
  },
  ivol: {
    en: "Idiosyncratic volatility: stock-specific volatility after removing market exposure. Stocks with low idiosyncratic vol tend to outperform (idiosyncratic vol puzzle).",
    zh: "個股波動率：剔除市場曝險後的個股特有波動。低個股波動率的股票往往表現較佳（個股波動率之謎）。",
  },
  skewness: {
    en: "Return distribution skewness. Stocks with highly positive skew (lottery-like payoffs) tend to be overpriced; negative skew stocks may offer a premium.",
    zh: "報酬分配偏態。具有高度正偏態（類彩票報酬）的股票往往被高估；負偏態股票可能提供溢價。",
  },
  max_ret: {
    en: "Maximum daily return over the past month. Stocks with extreme recent gains often reverse — another manifestation of the lottery effect.",
    zh: "過去一個月的最大單日報酬。近期極端上漲的股票常常反轉 — 彩票效應的另一種表現。",
  },

  // ── Backtest Metrics ──
  sharpe: {
    en: "Sharpe Ratio = (Annualized Return - Risk-Free Rate) / Annualized Volatility. Measures risk-adjusted performance; above 1.0 is good, above 2.0 is excellent.",
    zh: "夏普比率 =（年化報酬 - 無風險利率）/ 年化波動率。衡量風險調整績效；超過 1.0 為佳，超過 2.0 為優異。",
  },
  sortino: {
    en: "Sortino Ratio: like Sharpe but only penalizes downside volatility, not upside. Better reflects performance when returns are asymmetric.",
    zh: "索提諾比率：類似夏普比率但僅懲罰下行波動。報酬不對稱時更能反映真實績效。",
  },
  calmar: {
    en: "Calmar Ratio = Annualized Return / Maximum Drawdown. Measures return relative to the worst peak-to-trough loss. Higher is better; useful for drawdown-sensitive strategies.",
    zh: "卡瑪比率 = 年化報酬 / 最大回撤。衡量收益相對於最大峰谷損失的比率。數值越高越好，適用於對回撤敏感的策略。",
  },
  max_drawdown: {
    en: "Maximum Drawdown: the largest peak-to-trough decline in portfolio value. Shows the worst-case scenario an investor would have experienced.",
    zh: "最大回撤：投資組合從峰值到谷底的最大跌幅。顯示投資人可能經歷的最糟情境。",
  },
  total_return: {
    en: "Cumulative return over the entire backtest period: (Final NAV / Initial NAV) - 1. Does not account for the time elapsed.",
    zh: "回測期間的累計報酬：（期末淨值 / 期初淨值）- 1。未考慮經過的時間長度。",
  },
  annual_return: {
    en: "Compound Annual Growth Rate (CAGR): the annualized version of total return. Allows fair comparison across backtests of different durations.",
    zh: "複合年化成長率 (CAGR)：總報酬的年化版本。可公平比較不同時間長度的回測結果。",
  },
  win_rate: {
    en: "Percentage of trades that were profitable. A 60% win rate combined with a > 1 profit factor is typically a strong signal.",
    zh: "獲利交易佔總交易次數的百分比。60% 勝率搭配 > 1 的獲利因子通常是強勢信號。",
  },
  nav: {
    en: "Net Asset Value: the total market value of all holdings plus cash. Tracks portfolio performance over time.",
    zh: "淨資產價值：所有持倉的市值加上現金總額。用於追蹤投資組合隨時間的績效表現。",
  },

  // ── Risk Management ──
  kill_switch: {
    en: "Emergency mechanism that immediately liquidates all positions and halts all strategies. Triggered automatically at 5% daily drawdown or manually by risk managers.",
    zh: "緊急機制：立即平倉所有部位並停止所有策略。當日回撤達 5% 時自動觸發，或由風控經理手動啟動。",
  },
  daily_drawdown: {
    en: "Intraday portfolio decline from the day's peak value. Monitored in real-time; alerts at 2% (warning), 3% (critical), 5% (emergency kill switch).",
    zh: "投資組合在當日最高值至當前的跌幅。即時監控；2% 警告、3% 嚴重警告、5% 觸發緊急停止。",
  },
  position_weight: {
    en: "A single stock's market value as a percentage of total NAV. Capped to prevent over-concentration in one name (default limit: 10%).",
    zh: "單一股票市值佔總淨值的百分比。設有上限以防止過度集中（預設限制：10%）。",
  },
  fat_finger: {
    en: "Order price sanity check. Rejects limit orders whose price deviates from the market price by more than a threshold (default 5%). Guards against input typos.",
    zh: "訂單價格合理性檢查。當限價單價格偏離市場價格超過閾值（預設 5%）時拒絕執行。防止輸入錯誤。",
  },
  gross_leverage: {
    en: "Sum of all position absolute values / NAV. A leverage of 1.5x means the portfolio has 50% more exposure than its net asset value, amplifying both gains and losses.",
    zh: "所有部位絕對值之和 / 淨值。1.5 倍槓桿表示投資組合曝險比淨值多 50%，放大收益與損失。",
  },

  // ── Portfolio ──
  gross_exposure: {
    en: "Sum of all long positions + absolute value of all short positions, as % of NAV. Shows total market exposure regardless of direction.",
    zh: "所有多頭部位 + 所有空頭部位的絕對值之和，佔淨值百分比。顯示不論方向的總市場曝險。",
  },
  net_exposure: {
    en: "Long positions minus short positions, as % of NAV. Positive = net long (bullish), negative = net short (bearish), zero = market neutral.",
    zh: "多頭部位減去空頭部位，佔淨值百分比。正值 = 淨多頭（看漲）、負值 = 淨空頭（看跌）、零 = 市場中性。",
  },

  // ── Allocation ──
  tactical_allocation: {
    en: "Short-to-medium term deviations from strategic (long-term) asset class weights, driven by macro factors, cross-asset signals, and regime detection.",
    zh: "根據宏觀因子、跨資產信號和市場狀態偵測，對戰略（長期）資產類別權重進行短中期偏離調整。",
  },
  regime: {
    en: "Market regime classification: Bull (rising trend, low vol), Bear (falling trend, high vol), or Sideways (no clear trend). Different regimes favor different allocation tilts.",
    zh: "市場狀態分類：多頭（上升趨勢、低波動）、空頭（下跌趨勢、高波動）、盤整（無明確趨勢）。不同狀態適合不同的配置傾斜。",
  },
  risk_parity: {
    en: "Portfolio construction method that allocates capital so each asset class contributes equally to total portfolio risk, rather than allocating equal dollar amounts.",
    zh: "投資組合建構方法：配置資金使每個資產類別對總組合風險的貢獻相等，而非配置等額資金。",
  },
  black_litterman: {
    en: "Portfolio optimization model that combines market equilibrium returns with investor views to produce more stable, intuitive allocations than mean-variance optimization.",
    zh: "投資組合最佳化模型：結合市場均衡收益與投資人觀點，產生比均值-變異數最佳化更穩定、直觀的配置。",
  },
};
