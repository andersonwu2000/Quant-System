import { useT } from "@core/i18n";
import { Link } from "react-router-dom";

export function ChapterBacktest({ section }: { section?: string }) {
  const { lang } = useT();
  const t = (en: string, zh: string) => (lang === "zh" ? zh : en);

  if (section === "params-guide") return <ParamsGuideSection t={t} />;
  if (section === "reading-report") return <ReadingReportSection t={t} />;
  if (section === "common-pitfalls") return <CommonPitfallsSection t={t} />;
  return <WhatIsBacktestSection t={t} />;
}

type T = (en: string, zh: string) => string;

/* ------------------------------------------------------------------ */
/*  what-is-backtest                                                  */
/* ------------------------------------------------------------------ */
function WhatIsBacktestSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("What Is Backtesting?", "什麼是回測？")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Backtesting is the process of running your trading strategy on historical market data to see how it would have performed. You give the system a strategy, a set of stocks, and a date range, and it simulates every trade that would have been made — including transaction costs, slippage, and realistic constraints.",
          "回測是在歷史市場資料上運行你的交易策略，看看它過去會如何表現的過程。你給系統一個策略、一組股票和一個日期範圍，它會模擬每一筆交易 — 包括交易成本、滑價和現實約束。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Why Backtesting Matters", "為什麼回測重要")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "There's a saying in quantitative finance: \"Past performance doesn't guarantee future results, but a strategy that never worked in the past DEFINITELY won't work in the future.\" Backtesting is a necessary (but not sufficient) test. It answers the question: does this strategy have any historical evidence of working?",
          "量化金融界有句話：「過去的表現不保證未來結果，但一個過去從未有效的策略，未來絕對不會有效。」回測是必要（但非充分）的測試。它回答一個問題：這個策略有任何歷史證據支持它有效嗎？",
        )}
      </p>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Think of backtesting as a \"minimum bar\" — if a strategy can't even make money in historical simulation, there's no reason to risk real money on it. But passing backtesting doesn't guarantee future success. That's what paper trading is for.",
          "把回測想成「最低門檻」— 如果策略連歷史模擬中都不能賺錢，就沒有理由拿真金白銀去冒險。但通過回測不保證未來成功。那是模擬交易的用途。",
        )}
      </div>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("The Goal of Backtesting", "回測的目標")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The goal is NOT to find a strategy that maximizes historical returns. That leads to overfitting. The real goal is to find strategies that work consistently across different market conditions — bull markets, bear markets, sideways markets, high volatility, low volatility. A strategy with a modest 12% annual return that works in all environments is far more valuable than one with 50% returns that only works in bull markets.",
          "目標不是找到一個最大化歷史報酬的策略。那會導致過度擬合。真正的目標是找到在不同市場條件下穩定有效的策略 — 牛市、熊市、盤整市場、高波動、低波動。一個年化報酬率 12% 但在所有環境都有效的策略，遠比一個只在牛市有效、報酬率 50% 的策略更有價值。",
        )}
      </p>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t("Ready to run your first backtest? Head to the ", "準備好執行你的第一次回測了嗎？前往")}
        <Link to="/backtest" className="text-blue-600 dark:text-blue-400 underline underline-offset-2">
          {t("Backtest page", "回測頁面")}
        </Link>
        {t(".", "。")}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  params-guide                                                      */
/* ------------------------------------------------------------------ */
function ParamsGuideSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Parameter Guide", "參數設定指南")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Each backtest parameter affects the simulation's realism and results. Understanding what each parameter does helps you set up meaningful tests.",
          "每個回測參數都影響模擬的真實性和結果。了解每個參數的作用幫助你設置有意義的測試。",
        )}
      </p>

      {/* Strategy */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Strategy", "策略")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Which trading strategy to test. Available strategies include momentum, mean reversion, multi-factor, RSI oversold, MA crossover, pairs trading, sector rotation, and alpha (configurable factor pipeline). Each strategy has a different approach to generating trading signals. If you've completed alpha research, you can test your factor combination as the \"alpha\" strategy.",
          "要測試的交易策略。可用策略包括動量、均值回歸、多因子、RSI 超賣、均線交叉、配對交易、行業輪動和 alpha（可配置因子管道）。每個策略有不同的方法產生交易信號。如果你已完成 alpha 研究，可以將你的因子組合作為「alpha」策略測試。",
        )}
      </p>

      {/* Universe */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Universe", "股票池")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Which stocks to include in the backtest. A larger universe provides more diversification opportunities but makes the backtest slower. Recommendation: start with 20-50 stocks. You can use preset universes or manually select individual tickers. Make sure your universe includes enough stocks for meaningful statistical results.",
          "回測中包含哪些股票。較大的股票池提供更多分散化機會，但會讓回測更慢。建議：從 20-50 隻股票開始。你可以使用預設股票池或手動選擇個別股票代碼。確保你的股票池包含足夠多的股票以產生有意義的統計結果。",
        )}
      </p>

      {/* Date Range */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Start / End Date", "開始／結束日期")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The time period to simulate. Use at least 3-5 years to cover different market regimes (bull, bear, sideways). A backtest covering only a bull market will give misleadingly optimistic results. Ideally, your date range should include at least one significant drawdown (e.g., 2020 COVID crash, 2022 rate-hike selloff) to see how the strategy handles stress.",
          "要模擬的時間段。至少使用 3-5 年以涵蓋不同的市場狀態（牛市、熊市、盤整）。只涵蓋牛市的回測會給出誤導性的樂觀結果。理想情況下，你的日期範圍應包含至少一次重大回撤（如 2020 COVID 崩盤、2022 升息賣壓），以觀察策略如何應對壓力。",
        )}
      </p>

      {/* Initial Cash */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Initial Cash", "初始資金")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Starting capital for the simulation. Default is 1,000,000. This affects position sizing — with more capital you can hold more positions simultaneously. For Taiwan stocks, remember that lot size is 1,000 shares, so you need enough capital to buy at least one lot of each stock in your portfolio.",
          "模擬的初始資金。預設值為 1,000,000。這會影響部位大小 — 資金越多，你可以同時持有更多部位。對於台灣股票，記住交易單位是 1,000 股，所以你需要足夠的資金至少買入投資組合中每隻股票的一張。",
        )}
      </p>

      {/* Slippage */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Slippage (bps)", "滑價 (bps)")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Estimated cost of price impact when executing trades, measured in basis points (1 bps = 0.01%). Default is 5 bps (0.05%). When you place a market order, the actual execution price is usually slightly worse than the last traded price — this is slippage. Use higher values (10-20 bps) for illiquid stocks and lower values (2-5 bps) for highly liquid large-caps.",
          "執行交易時價格衝擊的估計成本，以基點衡量（1 bps = 0.01%）。預設為 5 bps（0.05%）。當你下市價單時，實際成交價通常比最後成交價略差 — 這就是滑價。對流動性差的股票使用較高值（10-20 bps），對流動性好的大型股使用較低值（2-5 bps）。",
        )}
      </p>

      {/* Commission */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Commission Rate", "手續費率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Trading cost charged by the broker. Taiwan default: 0.1425% per trade (both buy and sell). On the sell side, there's an additional 0.3% securities transaction tax. This means a full round-trip (buy + sell) costs approximately 0.585% before slippage. US stocks typically have zero commission but still incur slippage.",
          "券商收取的交易成本。台灣預設：每筆交易 0.1425%（買賣都收）。賣出時另有 0.3% 的證券交易稅。這意味著完整來回（買入+賣出）在滑價之前的成本約為 0.585%。美國股票通常零佣金，但仍有滑價。",
        )}
      </p>

      {/* Rebalance Frequency */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Rebalance Frequency", "再平衡頻率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "How often the strategy adjusts its positions. Daily rebalancing is the most responsive — the strategy reacts to new data every day — but generates the highest turnover and transaction costs. Weekly or monthly rebalancing reduces costs but is slower to react to changing market conditions. For most factor-based strategies, monthly rebalancing is a good starting point.",
          "策略多久調整一次部位。每日再平衡最靈敏 — 策略每天對新數據做出反應 — 但產生最高的周轉率和交易成本。每週或每月再平衡降低成本，但對市場變化的反應較慢。對大多數因子策略來說，每月再平衡是好的起點。",
        )}
      </p>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Tip: When in doubt, use the defaults. They're calibrated for Taiwan stock trading. Only change parameters when you have a specific reason — e.g., if you're trading US stocks, set commission to 0.",
          "提示：不確定時就使用預設值。它們是針對台灣股票交易校準的。只在有明確理由時更改參數 — 例如，如果你交易美國股票，將佣金設為 0。",
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  reading-report                                                    */
/* ------------------------------------------------------------------ */
function ReadingReportSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Reading Backtest Reports", "讀懂回測報告")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "After a backtest completes, you'll see a detailed report with performance metrics, charts, and trade history. Here's what each number means and what to look for.",
          "回測完成後，你會看到包含績效指標、圖表和交易歷史的詳細報告。以下是每個數字的含義和要關注的重點。",
        )}
      </p>

      {/* Total Return */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Total Return", "總報酬率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Cumulative return over the entire backtest period. A total return of 100% means you doubled your money. This is the most intuitive metric, but be careful: total return doesn't account for risk. A strategy that returns 100% but with a 60% drawdown is very different from one that returns 80% with only a 10% drawdown.",
          "整個回測期間的累積報酬率。總報酬率 100% 表示你的錢翻倍了。這是最直觀的指標，但要小心：總報酬率不考慮風險。一個報酬率 100% 但回撤 60% 的策略，與一個報酬率 80% 但回撤只有 10% 的策略截然不同。",
        )}
      </p>

      {/* CAGR */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Annual Return (CAGR)", "年化報酬率 (CAGR)")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Compound Annual Growth Rate — the annualized return that accounts for compounding. A 15% CAGR means your portfolio grows by 15% per year on average. This is more comparable across backtests of different lengths. Compare against benchmarks: Taiwan's TAIEX has historically returned ~8-10% annually; the S&P 500 ~10-12%.",
          "複合年均成長率 — 考慮複利效果的年化報酬率。15% 的 CAGR 表示你的投資組合平均每年成長 15%。這在不同長度的回測之間更具可比性。與基準比較：台灣加權指數歷史年化報酬約 8-10%；S&P 500 約 10-12%。",
        )}
      </p>

      {/* Sharpe */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Sharpe Ratio", "夏普比率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Return per unit of risk (volatility). This is arguably the single most important number. Sharpe = (annualized return - risk-free rate) / annualized volatility. A Sharpe of 1.0 means you earn 1% excess return for every 1% of risk. Guidelines: <0.5 = poor, 0.5-1.0 = acceptable, 1.0-2.0 = good, >2.0 = excellent (but check for overfitting if >3.0).",
          "每單位風險（波動率）的報酬。這可以說是最重要的單一數字。Sharpe = (年化報酬 - 無風險利率) / 年化波動率。夏普比率 1.0 表示每承擔 1% 的風險獲得 1% 的超額報酬。參考：<0.5 = 差、0.5-1.0 = 可接受、1.0-2.0 = 好、>2.0 = 優秀（但 >3.0 要檢查是否過度擬合）。",
        )}
      </p>

      {/* Max Drawdown */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Max Drawdown", "最大回撤")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The worst peak-to-trough decline during the backtest. If max drawdown is -20%, that means at the worst point, your portfolio lost 20% from its recent peak. Ask yourself: \"Can I stomach watching my portfolio drop by this much without panic-selling?\" Most individual investors can handle -10% to -15%. Professional funds target -20% to -25% max. Beyond -30% is very aggressive.",
          "回測期間最嚴重的從高點到低點的跌幅。如果最大回撤是 -20%，表示在最糟糕的時候，你的投資組合從近期高點下跌了 20%。問問自己：「我能忍受看著投資組合跌這麼多而不恐慌賣出嗎？」大多數個人投資者能承受 -10% 到 -15%。專業基金目標最大回撤 -20% 到 -25%。超過 -30% 非常激進。",
        )}
      </p>

      {/* Sortino */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Sortino Ratio", "索提諾比率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Like the Sharpe ratio, but only counts downside volatility as risk. The Sharpe penalizes upside volatility equally — but who complains about big positive returns? The Sortino gives a better picture for strategies with asymmetric returns (e.g., trend-following strategies that have large wins and small losses).",
          "類似夏普比率，但只把下行波動率算作風險。夏普比率同樣懲罰上行波動率 — 但誰會抱怨大幅正報酬呢？索提諾比率為報酬不對稱的策略（例如趨勢追蹤策略，有大贏小輸的特性）提供更好的視角。",
        )}
      </p>

      {/* Calmar */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Calmar Ratio", "Calmar 比率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Annual return divided by max drawdown. Measures return relative to your worst nightmare. A Calmar of 2.0 means you earn 2x the return of your worst drawdown — if max DD is -10%, you're making 20% per year. Higher is better. Calmar < 1.0 means your worst drawdown is larger than your annual return — that's uncomfortable.",
          "年化報酬率除以最大回撤。衡量報酬相對於你最糟情境的比值。Calmar 2.0 表示你的報酬是最大回撤的 2 倍 — 如果最大回撤是 -10%，你每年賺 20%。越高越好。Calmar < 1.0 表示你的最大回撤大於年化報酬 — 這讓人不安。",
        )}
      </p>

      {/* Win Rate */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Win Rate", "勝率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Percentage of profitable trades. A 60% win rate with average win > average loss is a strong strategy. Note: many profitable strategies have win rates below 50% — they make money by having large winners and small losers. Don't fixate on win rate alone; always consider it alongside average win vs. average loss size.",
          "獲利交易的百分比。60% 的勝率加上平均獲利 > 平均虧損是強勢策略。注意：許多獲利策略的勝率低於 50% — 它們靠大贏小輸賺錢。不要只關注勝率；要同時考慮平均獲利和平均虧損的大小。",
        )}
      </p>

      {/* NAV Curve */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("NAV Curve", "淨值曲線")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The chart showing your portfolio's value over time. Ideally it trends upward with manageable dips. A smooth, steadily rising curve is better than a volatile one — even if the volatile one has higher total returns. Look for: consistent upward slope (no long flat periods), recoveries from drawdowns within a few months, and no catastrophic drops.",
          "顯示你的投資組合淨值隨時間變化的圖表。理想情況下是穩步上升、回撤可控。一條平滑、穩定上升的曲線比波動劇烈的好 — 即使波動大的總報酬率更高。尋找：一致的上升斜率（沒有長期平坦期）、回撤後幾個月內恢復、沒有災難性下跌。",
        )}
      </p>

      {/* Decision Framework */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("When to Move Forward", "什麼時候可以繼續前進")}
      </h2>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "If Sharpe > 1.0, Max Drawdown > -15%, and the NAV curve looks smooth with consistent upward slope, consider moving to paper trading. These thresholds are conservative — professional quant funds often accept lower Sharpe ratios but with more sophisticated risk management.",
          "如果 Sharpe > 1.0、最大回撤 > -15%、淨值曲線平滑且持續向上，可以考慮進入模擬交易。這些門檻是保守的 — 專業量化基金通常接受較低的夏普比率，但有更複雜的風險管理。",
        )}
      </div>

      <div className="overflow-x-auto mb-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-surface-light">
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Metric", "指標")}</th>
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Red Flag", "紅旗")}</th>
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Acceptable", "可接受")}</th>
              <th className="text-left py-2 text-slate-700 dark:text-slate-300">{t("Strong", "優秀")}</th>
            </tr>
          </thead>
          <tbody className="text-slate-600 dark:text-slate-400">
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">CAGR</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;5%</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">5-15%</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;15%</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">Sharpe</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;0.5</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.5-1.0</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;1.0</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">{t("Max Drawdown", "最大回撤")}</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;-30%</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">-15% to -30%</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;-15%</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">Calmar</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;0.5</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.5-1.5</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;1.5</span></td>
            </tr>
            <tr>
              <td className="py-2 pr-4 font-medium">{t("Win Rate", "勝率")}</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;40%</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">40-55%</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;55%</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  common-pitfalls                                                   */
/* ------------------------------------------------------------------ */
function CommonPitfallsSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Common Pitfalls", "常見陷阱")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Backtesting is full of traps that can make a bad strategy look good. Understanding these pitfalls is the difference between a backtest that predicts real-world performance and one that's pure fiction.",
          "回測充滿了能讓壞策略看起來很好的陷阱。了解這些陷阱是回測能否預測真實世界表現，還是純粹虛構的關鍵差異。",
        )}
      </p>

      {/* 1. Overfitting */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("1. Overfitting", "1. 過度擬合")}
      </h2>

      <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
        <strong>{t("This is the #1 killer of quantitative strategies.", "這是量化策略的頭號殺手。")}</strong>{" "}
        {t(
          "Overfitting means your strategy has \"memorized\" the historical data rather than learning genuine patterns. It performs brilliantly on past data but fails on new data.",
          "過度擬合意味著你的策略「記住了」歷史數據，而非學到真正的規律。它在過去的數據上表現出色，但在新數據上失敗。",
        )}
      </div>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t("Warning signs of overfitting:", "過度擬合的警告信號：")}
      </p>

      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Too many parameters (>5 tunable settings = high risk)", "太多參數（>5 個可調設定 = 高風險）")}</li>
        <li>{t("Unrealistically high Sharpe ratio (>3.0 for a long-only strategy is suspicious)", "不切實際的高夏普比率（多頭策略 >3.0 令人起疑）")}</li>
        <li>{t("Strategy only works on a specific date range — shift the window by 6 months and it falls apart", "策略只在特定日期範圍有效 — 窗口移動 6 個月就崩壞")}</li>
        <li>{t("Performance degrades significantly in out-of-sample testing", "在樣本外測試中表現顯著下降")}</li>
      </ul>

      {/* 2. Survivorship Bias */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("2. Survivorship Bias", "2. 存活者偏差")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "If you only test stocks that exist today, you're ignoring all the stocks that went bankrupt or were delisted. This creates an upward bias — your universe is pre-filtered for winners. Imagine testing a strategy on \"the 50 largest Taiwan stocks\" but only using today's top 50. In 2018, some of those companies were small or didn't exist yet.",
          "如果你只測試現在存在的股票，你就忽略了所有破產或下市的股票。這創造了向上偏差 — 你的股票池預先篩選了贏家。想像一下用「台灣最大的 50 隻股票」測試策略，但只用今天的前 50 名。2018 年時，其中一些公司規模很小或尚未存在。",
        )}
      </p>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        <strong>{t("Mitigation:", "緩解方式：")}</strong>{" "}
        {t(
          "Use point-in-time universe data when available. At minimum, be aware this bias exists and interpret results conservatively.",
          "在可用時使用逐時間點的股票池數據。至少要意識到這種偏差的存在，保守地解讀結果。",
        )}
      </p>

      {/* 3. Look-ahead Bias */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("3. Look-ahead Bias", "3. 未來資訊偏差")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Using data that wouldn't have been available at the time of the trade. Example: using today's adjusted prices to make a decision that would have been made 3 years ago. Or using a financial report before its actual release date.",
          "使用在交易時尚不可用的數據。例如：用今天的調整後價格做一個 3 年前的決定。或在財報實際發布日期之前使用它。",
        )}
      </p>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Good news: Our system prevents look-ahead bias by design. The Context object truncates all data to the current simulation date, and HistoricalFeed enforces time boundaries. You don't need to worry about this one — the system handles it for you.",
          "好消息：我們的系統在設計上防止了未來資訊偏差。Context 物件會將所有數據截斷到當前模擬日期，HistoricalFeed 強制執行時間邊界。你不需要擔心這個 — 系統替你處理了。",
        )}
      </div>

      {/* 4. Transaction Cost Underestimation */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("4. Transaction Cost Underestimation", "4. 交易成本低估")}
      </h2>

      <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
        {t(
          "Many backtests assume zero or minimal trading costs. In reality, costs add up fast — especially for high-turnover strategies. For Taiwan stocks, a realistic round-trip cost is 60-80 basis points (commission + tax + slippage). If your strategy rebalances monthly and turns over 50% of the portfolio, that's 360-480 bps of annual cost drag. Your alpha must exceed this to be profitable.",
          "許多回測假設零或最小交易成本。實際上，成本累積很快 — 尤其是高周轉率策略。對台灣股票來說，真實的來回成本是 60-80 個基點（佣金 + 稅 + 滑價）。如果你的策略每月再平衡，周轉率 50%，那是每年 360-480 bps 的成本拖累。你的 alpha 必須超過這個才能獲利。",
        )}
      </div>

      {/* 5. Insufficient Sample Size */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("5. Insufficient Sample Size", "5. 樣本量不足")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "One year of data is not enough for a meaningful backtest. With monthly rebalancing, that's only 12 data points — far too few for statistical significance. Use at least 3-5 years. Ideally 7-10 years if data is available. More data means more market regimes covered, which gives you higher confidence that the strategy works in different environments.",
          "一年的數據不足以進行有意義的回測。以每月再平衡計算，那只有 12 個數據點 — 遠不足以達到統計顯著性。至少使用 3-5 年。如果數據可用，理想情況下 7-10 年。更多數據意味著涵蓋更多市場狀態，這讓你更有信心策略在不同環境下有效。",
        )}
      </p>

      {/* 6. Ignoring Regime Changes */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("6. Ignoring Regime Changes", "6. 忽視市場狀態變化")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "A strategy that only works in bull markets will eventually destroy you when the bear market arrives. Check your backtest results during different sub-periods: does the strategy make money in 2020 (COVID crash)? In 2022 (rate hike selloff)? In sideways markets? If performance is entirely concentrated in one regime, the strategy is fragile.",
          "一個只在牛市有效的策略，在熊市來臨時最終會摧毀你。檢查回測結果在不同子期間的表現：策略在 2020 年（COVID 崩盤）賺錢嗎？在 2022 年（升息拋售）呢？在盤整市場呢？如果表現完全集中在一個狀態，策略就是脆弱的。",
        )}
      </p>

      <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
        {t(
          "Final reminder: A backtest is an optimistic estimate. Real-world performance is almost always worse than backtest results due to factors that are hard to simulate: market impact, data errors, execution delays, and behavioral mistakes. Build in a safety margin — if a strategy barely passes your criteria in backtest, it will likely fail in live trading.",
          "最後提醒：回測是樂觀的估計。真實世界的表現幾乎總是比回測結果差，因為有些因素很難模擬：市場衝擊、數據錯誤、執行延遲和行為失誤。留出安全邊際 — 如果策略在回測中勉強通過你的標準，在實盤交易中很可能會失敗。",
        )}
      </div>
    </div>
  );
}
