import { useT } from "@core/i18n";
import { Link } from "react-router-dom";

export function ChapterAllocation({ section }: { section?: string }) {
  const { lang } = useT();
  const t = (en: string, zh: string) => (lang === "zh" ? zh : en);

  if (section === "macro-regime") return <MacroRegimeSection t={t} />;
  if (section === "optimizers") return <OptimizersSection t={t} />;
  return <StrategicVsTacticalSection t={t} />;
}

type T = (en: string, zh: string) => string;

/* ------------------------------------------------------------------ */
/*  strategic-vs-tactical                                              */
/* ------------------------------------------------------------------ */
function StrategicVsTacticalSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Strategic vs Tactical Allocation", "戰略配置 vs 戰術配置")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Asset allocation is the single most important decision in investing. Studies show that over 90% of a portfolio's return variability comes from allocation decisions, not individual stock picking. This system uses a two-layer approach: strategic allocation sets the long-term baseline, and tactical allocation adapts to current market conditions.",
          "資產配置是投資中最重要的決策。研究顯示，投資組合超過 90% 的報酬變異來自配置決策，而非個股選擇。本系統採用雙層方法：戰略配置設定長期基準，戰術配置則根據當前市場狀況進行調整。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Strategic Allocation", "戰略配置")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Strategic allocation defines your long-term target weights across asset classes. For example: 60% stocks, 30% bonds (via bond ETFs), 10% commodities (via commodity ETFs). This reflects your risk tolerance, investment horizon, and return goals. It changes rarely — typically reviewed once a year.",
          "戰略配置定義你在各資產類別的長期目標權重。例如：60% 股票、30% 債券（透過債券 ETF）、10% 商品（透過商品 ETF）。這反映了你的風險承受度、投資期限和報酬目標。它很少改變——通常每年檢視一次。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Determined by your risk profile and investment goals", "由你的風險偏好和投資目標決定")}</li>
        <li>{t("Reviewed annually or when life circumstances change", "每年檢視，或在人生階段改變時調整")}</li>
        <li>{t("Classic example: 60/40 stocks/bonds for moderate risk tolerance", "經典範例：60/40 股票/債券適合中等風險承受度")}</li>
        <li>{t("Young investors can hold more equities; near-retirement investors shift to bonds", "年輕投資者可多持股票；接近退休者轉向債券")}</li>
      </ul>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Tactical Allocation", "戰術配置")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Tactical allocation makes short-term deviations from strategic weights based on current market conditions. Think of it as: \"The market is in a bear regime, so reduce equity weight by 10% and move that to bonds.\" Tactical moves are temporary — you always drift back toward strategic weights when conditions normalize.",
          "戰術配置根據當前市場狀況對戰略權重進行短期偏離。可以這樣理解：「市場處於熊市狀態，所以將股票權重降低 10%，轉移至債券。」戰術調整是暫時的——當條件恢復正常時，你總是會回到戰略權重。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Based on macro factors, cross-asset signals, and market regime", "基於宏觀因子、跨資產信號和市場狀態")}</li>
        <li>{t("Adjustments are bounded — typically ±10% from strategic weights", "調整有限制——通常在戰略權重 ±10% 內")}</li>
        <li>{t("Rebalanced monthly or when signals change significantly", "每月再平衡，或信號顯著改變時調整")}</li>
      </ul>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Why Both Matter", "為什麼兩者都重要")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Strategic allocation sets the baseline — it determines your average return and risk over time. Tactical allocation adds value by adapting to conditions. Without strategic weights, you have no anchor. Without tactical adjustments, you miss opportunities to reduce drawdowns and enhance returns.",
          "戰略配置設定基準——它決定了你長期的平均報酬和風險。戰術配置透過適應市場狀況來增加價值。沒有戰略權重，你就沒有錨點。沒有戰術調整，你會錯過減少回撤和提升報酬的機會。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("How It Works in Our System", "在本系統中如何運作")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "You set strategic weights on the Allocation page. The system then computes tactical adjustments automatically based on three inputs: macro factors (growth, inflation, rates, credit from FRED data), cross-asset signals (momentum, volatility, value per asset class), and market regime (bull, bear, or sideways). The final allocation is your strategic weight plus tactical adjustment, constrained by risk rules.",
          "你在配置頁面設定戰略權重。然後系統會根據三個輸入自動計算戰術調整：宏觀因子（來自 FRED 數據的成長、通膨、利率、信用）、跨資產信號（每個資產類別的動量、波動率、價值）、以及市場狀態（牛市、熊市或盤整）。最終配置是你的戰略權重加上戰術調整，並受風控規則約束。",
        )}
      </p>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        <strong>{t("Real-world example:", "真實案例：")}</strong>{" "}
        {t(
          "During the COVID crash (2020 Q1), a tactical system would have detected deteriorating macro signals (credit spreads widening, growth indicators falling) and reduced equity allocation weeks before the bottom. This wouldn't predict the exact bottom, but it would have significantly reduced drawdown.",
          "在 COVID 崩盤期間（2020 年第一季），戰術系統會偵測到惡化的宏觀信號（信用利差擴大、成長指標下滑），並在觸底前數週減少股票配置。這不會預測確切的底部，但會顯著減少回撤。",
        )}
      </div>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Try it out on the ",
          "在",
        )}
        <Link to="/backtest" className="text-blue-600 dark:text-blue-400 underline underline-offset-2">
          {t("Backtest page", "回測頁面")}
        </Link>
        {t(
          " using the Multi-Asset strategy to see how allocation adjustments affect portfolio performance.",
          "使用多資產策略試試看，觀察配置調整如何影響投資組合表現。",
        )}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  macro-regime                                                       */
/* ------------------------------------------------------------------ */
function MacroRegimeSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Macro Factors & Market Regime", "宏觀因子與市場狀態")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The system monitors macroeconomic conditions to inform tactical allocation decisions. It tracks 4 macro factors derived from FRED (Federal Reserve Economic Data) and classifies the overall market into one of three regimes.",
          "系統監控宏觀經濟狀況以指導戰術配置決策。它追蹤從 FRED（聯準會經濟數據）衍生的 4 個宏觀因子，並將整體市場歸類為三種狀態之一。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("The 4 Macro Factors", "四大宏觀因子")}
      </h2>

      <h3 className="text-base font-semibold mt-4 mb-2 text-slate-800 dark:text-slate-200">
        {t("1. Growth", "1. 成長（Growth）")}
      </h3>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Tracks GDP growth and industrial production. A positive growth signal means the economy is expanding — favorable for equities and risky assets. Negative growth signals suggest contraction — shift toward bonds and defensive assets.",
          "追蹤 GDP 成長率和工業生產。正向成長信號表示經濟正在擴張——有利於股票和風險資產。負向成長信號暗示經濟收縮——應轉向債券和防禦性資產。",
        )}
      </p>

      <h3 className="text-base font-semibold mt-4 mb-2 text-slate-800 dark:text-slate-200">
        {t("2. Inflation", "2. 通膨（Inflation）")}
      </h3>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Monitors CPI (Consumer Price Index) and PPI (Producer Price Index). High inflation typically leads central banks to tighten monetary policy (raise rates), which is negative for both stocks and bonds. Low and stable inflation supports asset prices. Commodity ETFs can serve as inflation hedges.",
          "監控 CPI（消費者物價指數）和 PPI（生產者物價指數）。高通膨通常導致央行緊縮貨幣政策（升息），這對股票和債券都是負面的。低而穩定的通膨支持資產價格。商品 ETF 可作為通膨避險工具。",
        )}
      </p>

      <h3 className="text-base font-semibold mt-4 mb-2 text-slate-800 dark:text-slate-200">
        {t("3. Interest Rates", "3. 利率（Interest Rates）")}
      </h3>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Tracks the yield curve and Fed funds rate. An inverted yield curve (short-term rates higher than long-term) has historically been one of the most reliable recession indicators. When the yield curve inverts, the system becomes more cautious on equities.",
          "追蹤殖利率曲線和聯邦基金利率。殖利率曲線倒掛（短期利率高於長期利率）歷史上是最可靠的經濟衰退指標之一。當殖利率曲線倒掛時，系統對股票變得更謹慎。",
        )}
      </p>

      <h3 className="text-base font-semibold mt-4 mb-2 text-slate-800 dark:text-slate-200">
        {t("4. Credit", "4. 信用（Credit）")}
      </h3>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Monitors credit spreads (difference between corporate bond yields and Treasury yields) and default rates. Widening credit spreads signal increasing risk aversion — investors demand more compensation for holding risky debt. This is a strong risk-off signal that precedes equity market declines.",
          "監控信用利差（公司債殖利率與國債殖利率的差距）和違約率。信用利差擴大表示風險厭惡上升——投資者要求更多補償來持有風險債務。這是一個強烈的風險趨避信號，通常先於股市下跌出現。",
        )}
      </p>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "All macro factors are computed as z-scores (how many standard deviations from the historical mean). A z-score of +2 means the factor is 2 standard deviations above average — a very strong signal.",
          "所有宏觀因子都以 z 分數計算（距歷史平均值多少個標準差）。z 分數 +2 表示該因子高於平均值 2 個標準差——非常強烈的信號。",
        )}
      </div>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Market Regime Classification", "市場狀態分類")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Beyond macro factors, the system classifies the overall market into one of three regimes based on price trends and volatility:",
          "除了宏觀因子，系統還根據價格趨勢和波動率將整體市場歸類為三種狀態之一：",
        )}
      </p>

      <table className="w-full text-sm mb-4">
        <thead>
          <tr className="border-b border-slate-200 dark:border-surface-light">
            <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Regime", "狀態")}</th>
            <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Characteristics", "特徵")}</th>
            <th className="text-left py-2 text-slate-700 dark:text-slate-300">{t("Allocation Impact", "配置影響")}</th>
          </tr>
        </thead>
        <tbody className="text-slate-600 dark:text-slate-400">
          <tr className="border-b border-slate-100 dark:border-surface-light">
            <td className="py-2 pr-4 font-medium">{t("Bull", "牛市")}</td>
            <td className="py-2 pr-4">{t("Rising trend, low volatility", "上升趨勢、低波動率")}</td>
            <td className="py-2">{t("Overweight equities, reduce bonds", "增配股票、減配債券")}</td>
          </tr>
          <tr className="border-b border-slate-100 dark:border-surface-light">
            <td className="py-2 pr-4 font-medium">{t("Bear", "熊市")}</td>
            <td className="py-2 pr-4">{t("Falling trend, high volatility", "下降趨勢、高波動率")}</td>
            <td className="py-2">{t("Overweight bonds/cash, reduce equities", "增配債券/現金、減配股票")}</td>
          </tr>
          <tr>
            <td className="py-2 pr-4 font-medium">{t("Sideways", "盤整")}</td>
            <td className="py-2 pr-4">{t("No clear trend, moderate volatility", "無明確趨勢、中等波動率")}</td>
            <td className="py-2">{t("Stay close to strategic weights", "維持接近戰略權重")}</td>
          </tr>
        </tbody>
      </table>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("How Regime Affects Allocation", "市場狀態如何影響配置")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The tactical engine combines macro factor signals with the detected regime to produce weight adjustments. In a bull regime with strong growth and low inflation, the system aggressively tilts toward equities. In a bear regime with widening credit spreads, it reduces equity exposure and increases bond allocation.",
          "戰術引擎結合宏觀因子信號和偵測到的市場狀態來產生權重調整。在成長強勁且通膨低的牛市中，系統積極傾向股票。在信用利差擴大的熊市中，系統減少股票曝險並增加債券配置。",
        )}
      </p>

      <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
        <strong>{t("Practical advice:", "實用建議：")}</strong>{" "}
        {t(
          "Don't fight the regime. Even the best stock-picking alpha strategy struggles in a bear market. Respecting the macro environment and adjusting your allocation accordingly is the most effective way to protect capital during downturns.",
          "不要與市場狀態對抗。即使是最好的選股 alpha 策略在熊市中也會苦苦掙扎。尊重宏觀環境並相應調整配置，是在市場下跌期間保護資金最有效的方式。",
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  optimizers                                                         */
/* ------------------------------------------------------------------ */
function OptimizersSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Portfolio Optimization Methods", "投資組合最佳化方法")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Once you decide how much to allocate to each asset class, you need to decide how to weight individual assets within each class. The system provides 6 optimization methods, ranging from simple to sophisticated.",
          "一旦你決定了每個資產類別的配置比例，你需要決定如何在每個類別內為個別資產分配權重。系統提供 6 種最佳化方法，從簡單到複雜都有。",
        )}
      </p>

      {/* EW */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("1. Equal Weight (EW)", "1. 等權重（EW）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Give every asset equal weight. If you have 10 assets, each gets 10%. It sounds naive, but equal weight is a surprisingly effective baseline. It naturally rebalances by selling winners and buying losers (contrarian). Academic research shows equal-weight portfolios often outperform cap-weighted indices over long periods.",
          "給每個資產相同的權重。如果你有 10 個資產，每個分配 10%。聽起來很天真，但等權重是一個出奇有效的基準。它自然地透過賣出漲多的和買入跌多的進行再平衡（逆勢操作）。學術研究顯示，等權重投資組合在長期往往跑贏市值加權指數。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Pros: Simple, no estimation required, naturally contrarian", "優點：簡單、不需要估計、自然逆勢")}</li>
        <li>{t("Cons: Ignores risk — high-volatility assets get the same weight as low-volatility ones", "缺點：忽略風險——高波動資產與低波動資產權重相同")}</li>
      </ul>

      {/* Inverse Volatility */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("2. Inverse Volatility", "2. 反波動率（Inverse Volatility）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Weight each asset inversely proportional to its volatility. Less volatile assets get more weight, more volatile assets get less. This is a simple way to equalize risk contribution without complex optimization.",
          "按與波動率成反比的方式為每個資產分配權重。波動較低的資產獲得更多權重，波動較高的資產獲得較少。這是一種不需要複雜最佳化就能均衡風險貢獻的簡單方法。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Pros: Simple, risk-aware, only requires volatility estimates", "優點：簡單、考慮風險、只需要波動率估計")}</li>
        <li>{t("Cons: Ignores correlations between assets", "缺點：忽略資產間的相關性")}</li>
      </ul>

      {/* Risk Parity */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("3. Risk Parity", "3. 風險平價（Risk Parity）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Each asset contributes equally to total portfolio risk. This accounts for both volatility AND correlations. For example: \"Stocks are 3x more volatile than bonds, so bonds get roughly 3x the weight.\" Risk parity is the most popular institutional approach (used by Bridgewater's All Weather fund).",
          "每個資產對總投資組合風險的貢獻相等。這同時考慮了波動率和相關性。例如：「股票的波動是債券的 3 倍，所以債券大約獲得 3 倍的權重。」風險平價是最受歡迎的機構方法（Bridgewater 的全天候基金採用）。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Pros: Robust, accounts for correlations, well-diversified", "優點：穩健、考慮相關性、充分分散")}</li>
        <li>{t("Cons: May require leverage to achieve target returns (bonds have lower returns)", "缺點：可能需要槓桿來達到目標報酬（債券報酬較低）")}</li>
      </ul>

      {/* MVO */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("4. Mean-Variance Optimization (MVO)", "4. 均值-變異數最佳化（MVO）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The classic Markowitz optimization. Maximizes expected return for a given level of risk (or minimizes risk for a given return). This is the theoretical gold standard, but it has a critical weakness: it's extremely sensitive to input estimates. Small changes in expected returns can produce wildly different portfolios.",
          "經典的 Markowitz 最佳化。在給定風險水平下最大化預期報酬（或在給定報酬下最小化風險）。這是理論上的黃金標準，但它有一個關鍵弱點：對輸入估計極度敏感。預期報酬的小變化可能產生截然不同的投資組合。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Pros: Theoretically optimal, considers both return and risk", "優點：理論上最優、同時考慮報酬和風險")}</li>
        <li>{t("Cons: Garbage in, garbage out — very sensitive to estimation errors", "缺點：垃圾進垃圾出——對估計誤差非常敏感")}</li>
      </ul>

      <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
        {t(
          "MVO often produces extreme, concentrated portfolios. In practice, constraints (max weight, min weight) are always added, and the result is often not much better than simpler methods.",
          "MVO 經常產生極端、集中的投資組合。在實務上，總是會加入限制條件（最大權重、最小權重），結果通常不會比簡單方法好太多。",
        )}
      </div>

      {/* Black-Litterman */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("5. Black-Litterman", "5. Black-Litterman")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Combines market equilibrium (what the market \"thinks\" returns should be) with your personal views. For example: \"I think equities will outperform the equilibrium by 2% over the next year.\" The model blends your view with the market consensus, weighted by your confidence level. This produces much more stable portfolios than raw MVO.",
          "結合市場均衡（市場「認為」報酬應該是多少）和你的個人觀點。例如：「我認為股票在未來一年會比均衡報酬高出 2%。」模型會根據你的信心水平將你的觀點與市場共識混合。這比純 MVO 產生更穩定的投資組合。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Pros: Stable, incorporates views naturally, starts from a sensible baseline", "優點：穩定、自然地納入觀點、從合理的基線出發")}</li>
        <li>{t("Cons: Requires specifying views and confidence levels — extra complexity", "缺點：需要指定觀點和信心水平——增加複雜度")}</li>
      </ul>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The system supports BLView objects where you specify an asset, your expected excess return, and a confidence level (0 to 1). Higher confidence means the model tilts more toward your view.",
          "系統支援 BLView 物件，你可以指定資產、預期超額報酬和信心水平（0 到 1）。信心越高，模型越傾向你的觀點。",
        )}
      </p>

      {/* HRP */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("6. Hierarchical Risk Parity (HRP)", "6. 層次風險平價（HRP）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Uses hierarchical clustering to group similar assets, then allocates risk equally across clusters. This works particularly well when assets have complex correlation structures — it doesn't need to invert the covariance matrix (which is numerically unstable for large portfolios).",
          "使用層次聚類將相似資產分組，然後在各群組間平均分配風險。這在資產具有複雜相關結構時特別有效——它不需要對共變異數矩陣求逆（這對大型投資組合而言數值上不穩定）。",
        )}
      </p>
      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Pros: Handles many assets well, numerically stable, no return estimates needed", "優點：能處理大量資產、數值穩定、不需要報酬估計")}</li>
        <li>{t("Cons: Less intuitive than other methods, clustering can be sensitive to the lookback period", "缺點：不如其他方法直觀、聚類可能對回溯期間敏感")}</li>
      </ul>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Which Should You Choose?", "你應該選擇哪一個？")}
      </h2>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        <strong>{t("For beginners:", "給初學者：")}</strong>{" "}
        {t(
          "Start with Risk Parity. It's robust, intuitive, and doesn't require return forecasts. It naturally diversifies your portfolio and has been proven across many market environments.",
          "從 Risk Parity 開始。它穩健、直觀，而且不需要報酬預測。它自然地分散你的投資組合，已在許多市場環境中得到驗證。",
        )}
      </div>

      <table className="w-full text-sm mb-4">
        <thead>
          <tr className="border-b border-slate-200 dark:border-surface-light">
            <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Method", "方法")}</th>
            <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Complexity", "複雜度")}</th>
            <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Requires Returns?", "需要報酬估計？")}</th>
            <th className="text-left py-2 text-slate-700 dark:text-slate-300">{t("Best For", "最適合")}</th>
          </tr>
        </thead>
        <tbody className="text-slate-600 dark:text-slate-400">
          <tr className="border-b border-slate-100 dark:border-surface-light">
            <td className="py-2 pr-4">EW</td>
            <td className="py-2 pr-4">{t("Low", "低")}</td>
            <td className="py-2 pr-4">{t("No", "否")}</td>
            <td className="py-2">{t("Quick baseline", "快速基準")}</td>
          </tr>
          <tr className="border-b border-slate-100 dark:border-surface-light">
            <td className="py-2 pr-4">Inverse Vol</td>
            <td className="py-2 pr-4">{t("Low", "低")}</td>
            <td className="py-2 pr-4">{t("No", "否")}</td>
            <td className="py-2">{t("Simple risk-aware", "簡單風險感知")}</td>
          </tr>
          <tr className="border-b border-slate-100 dark:border-surface-light">
            <td className="py-2 pr-4">Risk Parity</td>
            <td className="py-2 pr-4">{t("Medium", "中")}</td>
            <td className="py-2 pr-4">{t("No", "否")}</td>
            <td className="py-2">{t("Most investors", "大部分投資者")}</td>
          </tr>
          <tr className="border-b border-slate-100 dark:border-surface-light">
            <td className="py-2 pr-4">MVO</td>
            <td className="py-2 pr-4">{t("High", "高")}</td>
            <td className="py-2 pr-4">{t("Yes", "是")}</td>
            <td className="py-2">{t("Experienced users", "有經驗的使用者")}</td>
          </tr>
          <tr className="border-b border-slate-100 dark:border-surface-light">
            <td className="py-2 pr-4">Black-Litterman</td>
            <td className="py-2 pr-4">{t("High", "高")}</td>
            <td className="py-2 pr-4">{t("Views only", "僅觀點")}</td>
            <td className="py-2">{t("Active views + stability", "主動觀點 + 穩定性")}</td>
          </tr>
          <tr>
            <td className="py-2 pr-4">HRP</td>
            <td className="py-2 pr-4">{t("Medium", "中")}</td>
            <td className="py-2 pr-4">{t("No", "否")}</td>
            <td className="py-2">{t("Large, complex portfolios", "大型、複雜投資組合")}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
