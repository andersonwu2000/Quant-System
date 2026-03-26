import { useT } from "@core/i18n";
import { Link } from "react-router-dom";

export function ChapterAlpha({ section }: { section?: string }) {
  const { lang } = useT();
  const t = (en: string, zh: string) => (lang === "zh" ? zh : en);

  if (section === "factor-catalog") return <FactorCatalogSection t={t} />;
  if (section === "choosing-factors") return <ChoosingFactorsSection t={t} />;
  if (section === "reading-results") return <ReadingResultsSection t={t} />;
  if (section === "alpha-walkthrough") return <AlphaWalkthroughSection t={t} />;
  return <WhatAreFactorsSection t={t} />;
}

type T = (en: string, zh: string) => string;

/* ------------------------------------------------------------------ */
/*  what-are-factors                                                  */
/* ------------------------------------------------------------------ */
function WhatAreFactorsSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("What Are Factors?", "什麼是因子？")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "A factor is a measurable characteristic of a stock that has historically been associated with higher (or lower) future returns. Think of it as a quantifiable \"trait\" — like how being tall helps in basketball, certain stock traits help predict performance.",
          "因子是股票的一種可量化特徵，歷史上與未來更高（或更低）的報酬相關。把它想成可量化的「特質」— 就像身高在籃球中有優勢一樣，某些股票特質有助於預測表現。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("The Recipe Analogy", "食譜比喻")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Think of building an alpha model like cooking. Each factor is an ingredient — momentum is salt, volatility is pepper, mean reversion is garlic. The alpha model is your recipe: how much of each ingredient to use, and how to combine them. A good recipe uses complementary ingredients in the right proportions. Too much of one thing ruins the dish. And just like cooking, the best results come from understanding WHY each ingredient works, not just throwing everything in.",
          "把建立 alpha 模型想像成做菜。每個因子是一種食材 — 動量是鹽、波動率是胡椒、均值回歸是大蒜。Alpha 模型就是你的食譜：每種食材用多少、如何組合。好的食譜使用互補的食材，比例恰到好處。某一種太多會毀了整道菜。就像烹飪一樣，最好的結果來自理解每種食材「為什麼」有效，而不只是什麼都丟進去。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Why Do Factors Work?", "因子為什麼有效？")}
      </h2>

      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>
          <strong>{t("Market inefficiencies", "市場無效率")}</strong> — {t("not all information is instantly reflected in prices. Factors exploit the delay.", "並非所有資訊都即時反映在價格中。因子利用的就是這種延遲。")}
        </li>
        <li>
          <strong>{t("Behavioral biases", "行為偏誤")}</strong> — {t("investors systematically overreact, underreact, or follow the herd. These biases create predictable patterns.", "投資者系統性地過度反應、反應不足或跟風。這些偏誤創造了可預測的模式。")}
        </li>
        <li>
          <strong>{t("Risk premia", "風險溢酬")}</strong> — {t("some stocks are riskier in ways that aren't obvious. Investors demand higher returns for bearing these risks, which creates persistent return differences.", "有些股票的風險方式不明顯。投資者要求更高報酬來承擔這些風險，這創造了持續的報酬差異。")}
        </li>
      </ul>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("The Cross-Sectional Approach", "橫截面方法")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Unlike traditional stock picking (\"I think TSMC will go up\"), factor investing ranks ALL stocks in your universe by a factor, then buys the top-ranked stocks and avoids (or shorts) the bottom-ranked ones. This approach is:",
          "不同於傳統選股（「我覺得台積電會漲」），因子投資對你的股票池中的所有股票按因子排名，然後買入排名最高的股票，迴避（或放空）排名最低的。這種方法是：",
        )}
      </p>

      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li><strong>{t("Systematic", "系統化的")}</strong> — {t("same rules apply to every stock, every period", "相同的規則適用於每隻股票、每個時期")}</li>
        <li><strong>{t("Repeatable", "可重複的")}</strong> — {t("not dependent on one-time insights or luck", "不依賴一次性洞見或運氣")}</li>
        <li><strong>{t("Emotion-free", "無情緒的")}</strong> — {t("the model decides, not your fear or greed", "模型做決定，而非你的恐懼或貪婪")}</li>
      </ul>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Key insight: You don't need to predict whether the market goes up or down. You just need to predict which stocks will do RELATIVELY better than others. This is much easier.",
          "關鍵洞見：你不需要預測市場漲跌。你只需要預測哪些股票「相對」表現更好。這容易得多。",
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  factor-catalog                                                    */
/* ------------------------------------------------------------------ */
function FactorCatalogSection({ t }: { t: T }) {
  const factors = [
    {
      nameEn: "Momentum",
      nameZh: "動量",
      measureEn: "Past 12-month return (skipping the most recent month). Captures medium-term price trends.",
      measureZh: "過去 12 個月報酬（跳過最近一個月）。捕捉中期價格趨勢。",
      whyEn: "Winners keep winning because of slow information diffusion, herding behavior, and confirmation bias. Investors underreact to good news, so the price continues to drift upward.",
      whyZh: "贏家繼續贏是因為資訊擴散緩慢、羊群行為和確認偏誤。投資者對好消息反應不足，所以價格持續向上漂移。",
      whenEn: "Works best in trending markets with clear direction. Fails badly during sharp reversals (\"momentum crashes\"), typically when markets transition from bear to bull.",
      whenZh: "在方向明確的趨勢市場中效果最好。在急劇反轉時嚴重失敗（「動量崩潰」），通常發生在市場從熊轉牛時。",
      direction: t("Higher = better (buy past winners)", "越高越好（買入過去贏家）"),
    },
    {
      nameEn: "Mean Reversion",
      nameZh: "均值回歸",
      measureEn: "Z-score of price relative to its moving average. Measures how far a stock has deviated from its \"normal\" level.",
      measureZh: "價格相對於移動平均的 Z 分數。衡量股票偏離其「正常」水位的程度。",
      whyEn: "Oversold stocks bounce back because the selling was driven by panic or forced liquidation, not fundamentals. Short-term overreaction creates buying opportunities.",
      whyZh: "超賣股票反彈是因為賣壓來自恐慌或強制清算，而非基本面。短期過度反應創造了買入機會。",
      whenEn: "Works best in range-bound, choppy markets. Fails in strong trend markets where \"cheap\" stocks keep getting cheaper.",
      whenZh: "在盤整、震盪的市場中效果最好。在強趨勢市場中失敗，因為「便宜」的股票持續變得更便宜。",
      direction: t("Lower = better (buy oversold)", "越低越好（買入超賣）"),
    },
    {
      nameEn: "Volatility",
      nameZh: "波動率",
      measureEn: "Annualized standard deviation of daily returns. Measures how much a stock's price swings.",
      measureZh: "日報酬的年化標準差。衡量股票價格波動的幅度。",
      whyEn: "The \"low-volatility anomaly\": low-vol stocks outperform on a risk-adjusted basis because investors overpay for exciting, volatile stocks (like lottery tickets) while boring, stable stocks are underpriced.",
      whyZh: "「低波動率異常」：低波動率股票在風險調整基礎上表現更好，因為投資者為刺激的、高波動的股票（像彩券一樣）支付過高價格，而無聊穩定的股票被低估。",
      whenEn: "Works consistently across most market regimes. Tends to underperform in strong bull markets when speculative stocks soar.",
      whenZh: "在大多數市場狀態下表現穩定。在強勁牛市中，當投機股飆漲時，傾向於表現不佳。",
      direction: t("Lower = better (buy low-vol)", "越低越好（買入低波動率）"),
    },
    {
      nameEn: "RSI",
      nameZh: "RSI 相對強弱指標",
      measureEn: "Relative Strength Index — ratio of recent gains to recent losses over 14 days. RSI below 30 signals oversold conditions.",
      measureZh: "相對強弱指標 — 14 天內近期漲幅與跌幅的比率。RSI 低於 30 表示超賣。",
      whyEn: "Extreme selling creates temporary mispricings. When RSI drops below 30, it often means the selling pressure is exhausted and a bounce is likely.",
      whyZh: "極端賣壓創造暫時的錯誤定價。當 RSI 跌破 30 時，通常意味著賣壓已耗盡，反彈可能即將到來。",
      whenEn: "Works well for timing entries in stocks that are fundamentally sound but temporarily depressed. Fails when the stock is declining for fundamental reasons (\"catching a falling knife\").",
      whenZh: "在基本面良好但暫時被壓低的股票中，很適合作為進場時機。當股票因基本面原因下跌時會失敗（「接飛刀」）。",
      direction: t("Lower = better (buy when RSI < 30)", "越低越好（RSI < 30 時買入）"),
    },
    {
      nameEn: "MA Cross",
      nameZh: "均線交叉",
      measureEn: "Signal generated when a fast moving average (e.g. 10-day) crosses above a slow moving average (e.g. 50-day). Captures trend initiation.",
      measureZh: "當快速移動平均線（如 10 日）向上穿越慢速移動平均線（如 50 日）時產生信號。捕捉趨勢啟動。",
      whyEn: "Moving average crossovers smooth out noise and confirm that a trend has genuinely started. They filter out random price fluctuations.",
      whyZh: "均線交叉平滑雜訊並確認趨勢確實已經開始。它們過濾掉隨機的價格波動。",
      whenEn: "Works in trending markets. Generates many false signals (\"whipsaws\") in sideways markets, leading to excessive trading and losses.",
      whenZh: "在趨勢市場中有效。在橫盤市場中產生許多假信號（「鞭打」），導致過度交易和虧損。",
      direction: t("Bullish cross = buy signal", "黃金交叉 = 買入信號"),
    },
    {
      nameEn: "Volume-Price Trend",
      nameZh: "量價趨勢",
      measureEn: "Combines price movement with trading volume to detect accumulation (quiet buying) or distribution (quiet selling).",
      measureZh: "結合價格變動與交易量來偵測吸貨（安靜買入）或出貨（安靜賣出）。",
      whyEn: "Smart money (institutions) often accumulates positions gradually. Rising prices on increasing volume confirms genuine demand; rising prices on declining volume suggests weak buying.",
      whyZh: "聰明資金（機構法人）通常漸進式地累積部位。價格上漲伴隨成交量增加，確認真實需求；價格上漲但成交量下降，暗示買盤薄弱。",
      whenEn: "Works well in markets with clear institutional activity. Less reliable in low-liquidity stocks where a few large orders can distort volume signals.",
      whenZh: "在機構活動明顯的市場中效果好。在低流動性股票中不太可靠，因為幾筆大單就能扭曲成交量信號。",
      direction: t("Positive accumulation = bullish", "正向吸貨 = 看多"),
    },
    {
      nameEn: "Reversal",
      nameZh: "反轉",
      measureEn: "Extreme short-term losers over 1-4 weeks. Captures quick mean-reversion at shorter horizons than the standard mean reversion factor.",
      measureZh: "1-4 週內的極端短期輸家。在比標準均值回歸因子更短的週期內捕捉快速均值回歸。",
      whyEn: "Short-term overreaction to news, liquidity shocks, or forced selling creates temporary mispricings that correct within days to weeks.",
      whyZh: "對新聞、流動性衝擊或強制賣出的短期過度反應，創造了在數天到數週內修正的暫時錯誤定價。",
      whenEn: "Works after sharp sell-offs. Fails when the decline is driven by genuine negative information (earnings miss, fraud, etc.).",
      whenZh: "在急跌後有效。當下跌是由真正的負面資訊驅動時（財報不佳、造假等）則會失敗。",
      direction: t("Lower (bigger loser) = better", "越低（跌越多）= 越好"),
    },
    {
      nameEn: "Illiquidity",
      nameZh: "流動性不足",
      measureEn: "Amihud illiquidity ratio: absolute return divided by dollar volume. Higher ratio = less liquid.",
      measureZh: "Amihud 非流動性比率：絕對報酬除以成交金額。比率越高 = 流動性越差。",
      whyEn: "Illiquid stocks carry a premium because investors demand compensation for the risk of not being able to exit quickly. This is a genuine risk premium, not a mispricing.",
      whyZh: "非流動性股票有溢酬，因為投資者要求補償無法快速退出的風險。這是真正的風險溢酬，而非錯誤定價。",
      whenEn: "Works consistently over long horizons. Beware: illiquid stocks have high trading costs, which can eat into the premium. Best for patient, long-term investors.",
      whenZh: "在長期表現穩定。注意：非流動性股票交易成本高，可能侵蝕溢酬。最適合有耐心的長期投資者。",
      direction: t("Higher = better (buy illiquid)", "越高越好（買入低流動性）"),
    },
    {
      nameEn: "Idiosyncratic Volatility",
      nameZh: "個股波動率",
      measureEn: "Stock-specific volatility after removing market-wide and sector effects. Measures the \"unique\" risk of each stock.",
      measureZh: "移除市場和產業效應後的個股特有波動率。衡量每隻股票的「獨特」風險。",
      whyEn: "Stocks with high idiosyncratic vol tend to be lottery-like — investors overpay for the chance of a big win, similar to the volatility anomaly. Low idio-vol stocks are more predictable and better risk-adjusted investments.",
      whyZh: "高個股波動率的股票往往像彩券 — 投資者為大贏的機會支付過高價格，類似波動率異常。低個股波動率的股票更可預測，風險調整後表現更好。",
      whenEn: "Works across most regimes. Particularly strong after periods of high market uncertainty when investors flock to quality.",
      whenZh: "在大多數狀態下有效。在市場高度不確定、投資者湧向品質股時特別強勢。",
      direction: t("Lower = better (buy low idio-vol)", "越低越好（買入低個股波動率）"),
    },
    {
      nameEn: "Skewness",
      nameZh: "偏態",
      measureEn: "The asymmetry of a stock's return distribution. Positive skew means occasional extreme positive returns (\"lottery-like\").",
      measureZh: "股票報酬分佈的不對稱性。正偏態表示偶爾出現極端正報酬（「彩券型」）。",
      whyEn: "Investors are attracted to stocks with lottery-like payoffs and are willing to overpay for them. This \"skewness preference\" leads to lower average returns for positively skewed stocks.",
      whyZh: "投資者被具有彩券般報酬的股票吸引，願意為此支付過高價格。這種「偏態偏好」導致正偏態股票的平均報酬較低。",
      whenEn: "Works in markets where retail speculation is common (like Taiwan!). Less effective in markets dominated by institutional investors.",
      whenZh: "在散戶投機活躍的市場有效（像台灣！）。在機構投資者主導的市場效果較差。",
      direction: t("Negative skew = better (avoid lottery stocks)", "負偏態 = 更好（迴避彩券型股票）"),
    },
    {
      nameEn: "Max Return",
      nameZh: "最大報酬",
      measureEn: "The highest single-day return in the past month. Captures stocks that have had extreme recent spikes.",
      measureZh: "過去一個月內最高的單日報酬。捕捉近期有極端飆漲的股票。",
      whyEn: "Extreme recent gainers attract attention and speculative buying, which pushes prices above fair value. The subsequent reversal generates negative returns. Related to the skewness effect.",
      whyZh: "近期極端贏家吸引注意力和投機性買入，將價格推高到公允價值之上。隨後的反轉產生負報酬。與偏態效應相關。",
      whenEn: "Works as a contrarian signal. Best when combined with other factors to avoid value traps.",
      whenZh: "作為反向信號有效。最好與其他因子組合使用，以避免價值陷阱。",
      direction: t("Lower = better (avoid recent extreme gainers)", "越低越好（迴避近期極端贏家）"),
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Factor Catalog", "因子詳解")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Below is a detailed explanation of every factor available in the system. For each factor, we explain what it measures, why it works, when it works best (and worst), and the typical signal direction.",
          "以下是系統中每個可用因子的詳細說明。對於每個因子，我們解釋它衡量什麼、為什麼有效、在什麼時候最有效（以及最無效），以及典型的信號方向。",
        )}
      </p>

      {factors.map((f, idx) => (
        <div key={idx} className="mb-6 p-4 rounded-lg border border-slate-200 dark:border-surface-light">
          <h2 className="text-lg font-semibold mb-3 text-slate-800 dark:text-slate-200">
            {idx + 1}. {t(f.nameEn, f.nameZh)}{" "}
            {f.nameEn !== t(f.nameEn, f.nameZh) && (
              <span className="text-sm font-normal text-slate-400">({f.nameEn})</span>
            )}
          </h2>

          <div className="space-y-2">
            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              <strong>{t("What it measures:", "衡量什麼：")}</strong> {t(f.measureEn, f.measureZh)}
            </p>
            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              <strong>{t("Why it works:", "為什麼有效：")}</strong> {t(f.whyEn, f.whyZh)}
            </p>
            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              <strong>{t("When it works:", "什麼時候有效：")}</strong> {t(f.whenEn, f.whenZh)}
            </p>
            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              <strong>{t("Direction:", "方向：")}</strong>{" "}
              <span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">
                {f.direction}
              </span>
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  choosing-factors                                                  */
/* ------------------------------------------------------------------ */
function ChoosingFactorsSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Choosing Factor Combinations", "如何選擇因子組合")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Selecting the right combination of factors is more important than finding a single powerful factor. A well-diversified factor portfolio is more robust than relying on any one signal.",
          "選擇正確的因子組合比找到單一強力因子更重要。一個多元化的因子組合比依賴任何單一信號更穩健。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Rule 1: Don't Use All Factors At Once", "規則 1：不要同時使用所有因子")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Pick 3-5 factors that are conceptually different. More factors means more noise, more parameters to tune, and more opportunities for overfitting. A simple model with 3 well-chosen factors will almost always beat a complex model with 10 factors.",
          "選擇 3-5 個概念上不同的因子。越多因子意味著越多雜訊、越多需要調整的參數、越多過度擬合的機會。一個精選 3 個因子的簡單模型幾乎總是會打敗一個使用 10 個因子的複雜模型。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Rule 2: Combine Complementary Styles", "規則 2：組合互補的風格")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Trend-following factors (momentum, MA cross) and contrarian factors (mean reversion, reversal) tend to work in different market environments. Combining them provides diversification across market regimes. When momentum fails (market reversals), mean reversion often picks up the slack, and vice versa.",
          "趨勢追蹤因子（動量、均線交叉）和反向因子（均值回歸、反轉）往往在不同的市場環境中有效。組合它們提供了跨市場狀態的分散化。當動量失效時（市場反轉），均值回歸通常能接手，反之亦然。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Rule 3: Check Factor Correlations", "規則 3：檢查因子相關性")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "If two factors are highly correlated (e.g. momentum and MA cross both capture trends), using both adds noise, not signal. The Alpha Research page shows factor correlations — look for factors with low or negative correlations to each other. That's where diversification benefit comes from.",
          "如果兩個因子高度相關（例如動量和均線交叉都捕捉趨勢），同時使用只會增加雜訊，而非信號。Alpha 研究頁面顯示因子相關性 — 尋找彼此低相關或負相關的因子。分散化效益就來自於此。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Rule 4: Consider Your Market", "規則 4：考慮你的市場")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The Taiwan stock market has different characteristics than the US market. Taiwan has more retail participation, which strengthens behavioral factors (momentum, reversal, skewness). The US market is more efficient and institutional-dominated, so factor premiums tend to be smaller but more persistent. Always validate your factors on your target market — don't assume what works in the US works in Taiwan.",
          "台灣股市有不同於美國市場的特性。台灣有更多散戶參與，這強化了行為因子（動量、反轉、偏態）。美國市場效率更高、由機構主導，所以因子溢酬通常較小但更持久。永遠在你的目標市場上驗證因子 — 不要假設在美國有效的在台灣也有效。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Beginner Recommendation", "新手推薦")}
      </h2>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Start with these three factors: Momentum + Mean Reversion + Volatility. This combination covers trend-following (momentum), contrarian (mean reversion), and risk-based (volatility) styles. It's well-diversified and has strong academic support. Once you're comfortable, experiment by swapping in other factors one at a time.",
          "從這三個因子開始：動量 + 均值回歸 + 波動率。這個組合涵蓋了趨勢追蹤（動量）、反向（均值回歸）和風險基礎（波動率）風格。它分散化良好，有強力的學術支持。等你熟悉後，再嘗試一次替換一個其他因子。",
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  reading-results                                                   */
/* ------------------------------------------------------------------ */
function ReadingResultsSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Reading Research Results", "讀懂研究結果")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "After running an alpha research analysis, you'll see a table of metrics for each factor. Here's what each metric means and how to interpret it.",
          "執行 alpha 研究分析後，你會看到每個因子的指標表。以下是每個指標的含義和解讀方式。",
        )}
      </p>

      {/* IC */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("IC (Information Coefficient)", "IC（資訊係數）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The correlation between the factor's prediction and actual future returns. Ranges from -1 to +1. An IC of 0 means no predictive power; IC > 0.03 is considered a meaningful signal. Example: if IC = 0.05, the factor correctly ranks stocks about 52.5% of the time — sounds small, but applied across hundreds of stocks over many periods, it compounds into significant alpha.",
          "因子預測與實際未來報酬之間的相關性。範圍從 -1 到 +1。IC 為 0 表示沒有預測力；IC > 0.03 被認為是有意義的信號。例如：如果 IC = 0.05，因子約 52.5% 的時間能正確排名股票 — 聽起來很小，但應用在數百隻股票、多個時期後，會累積成顯著的 alpha。",
        )}
      </p>

      {/* ICIR */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("ICIR (IC Information Ratio)", "ICIR（IC 資訊比率）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "IC Mean divided by IC Standard Deviation. Measures the CONSISTENCY of the factor's predictive power. ICIR > 0.5 means the factor works reliably across time periods. This is arguably more important than IC itself — a factor with IC=0.03 and ICIR=0.8 is BETTER than one with IC=0.06 and ICIR=0.3, because consistency matters more than peak performance.",
          "IC 平均值除以 IC 標準差。衡量因子預測力的「一致性」。ICIR > 0.5 表示因子在不同時期都能可靠地運作。這可以說比 IC 本身更重要 — IC=0.03 且 ICIR=0.8 的因子比 IC=0.06 且 ICIR=0.3 的因子更好，因為一致性比峰值表現更重要。",
        )}
      </p>

      {/* Hit Rate */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Hit Rate", "命中率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The percentage of time periods where IC > 0. A hit rate > 55% means the factor works more often than not. Hit rate below 50% means the factor is wrong more often than right — avoid it.",
          "IC > 0 的時期占比。命中率 > 55% 表示因子在多數時候有效。命中率低於 50% 表示因子錯的時候比對的時候多 — 應避免使用。",
        )}
      </p>

      {/* L/S Sharpe */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("L/S Sharpe (Long/Short Sharpe Ratio)", "L/S Sharpe（多空夏普比率）")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The Sharpe ratio of a portfolio that goes long the top quintile and short the bottom quintile. This isolates the factor's return from market direction. A L/S Sharpe > 0.5 suggests the factor is economically meaningful — it generates real returns after accounting for risk.",
          "做多最高五分位、做空最低五分位的投資組合的夏普比率。這將因子報酬從市場方向中隔離出來。L/S Sharpe > 0.5 表示因子在經濟上有意義 — 考慮風險後能產生真實報酬。",
        )}
      </p>

      {/* Monotonicity */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Monotonicity", "單調性")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Do quantile returns increase smoothly from Q1 to Q5? A monotonicity score of 1.0 means perfect ordering (Q5 > Q4 > Q3 > Q2 > Q1). Below 0.5 means the relationship is noisy and unreliable. Good monotonicity confirms the factor has a clear, linear relationship with returns.",
          "分位報酬是否從 Q1 到 Q5 平滑遞增？單調性分數 1.0 表示完美排序（Q5 > Q4 > Q3 > Q2 > Q1）。低於 0.5 表示關係雜訊多且不可靠。良好的單調性確認因子與報酬有清晰的線性關係。",
        )}
      </p>

      {/* Turnover */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Turnover", "周轉率")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "How much the portfolio changes each rebalancing period, measured as a fraction of total portfolio value. High turnover means high transaction costs. A factor with 80% monthly turnover replaces 80% of its holdings every month — that's expensive. Low turnover factors (< 30%) are cheaper to implement.",
          "每次再平衡時投資組合變動多少，以投資組合總值的比例衡量。高周轉率意味著高交易成本。每月周轉率 80% 的因子每月替換 80% 的持股 — 這非常昂貴。低周轉率因子（< 30%）實施成本較低。",
        )}
      </p>

      {/* Cost Drag & Breakeven */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Cost Drag & Breakeven Cost", "成本拖累與損益平衡成本")}
      </h2>
      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Cost Drag is the annual cost of trading the factor portfolio, measured in basis points (1 bp = 0.01%). If the factor generates 200 bps of alpha but cost drag is 250 bps, you lose money after costs. Breakeven Cost is the maximum transaction cost the factor can tolerate while remaining profitable. If your actual round-trip cost is 70 bps and the breakeven cost is 50 bps, this factor is NOT tradeable for you.",
          "成本拖累是交易因子組合的年化成本，以基點衡量（1 bp = 0.01%）。如果因子產生 200 bps 的 alpha，但成本拖累是 250 bps，扣除成本後你是虧損的。損益平衡成本是因子能承受的最大交易成本。如果你的實際來回成本是 70 bps，而損益平衡成本是 50 bps，這個因子對你來說是不可交易的。",
        )}
      </p>

      {/* Reference Table */}
      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Quick Reference Table", "快速參考表")}
      </h2>

      <div className="overflow-x-auto mb-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-surface-light">
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Metric", "指標")}</th>
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Poor", "差")}</th>
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Acceptable", "可接受")}</th>
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Good", "好")}</th>
              <th className="text-left py-2 text-slate-700 dark:text-slate-300">{t("Excellent", "優秀")}</th>
            </tr>
          </thead>
          <tbody className="text-slate-600 dark:text-slate-400">
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">IC Mean</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;0.01</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.01-0.03</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.03-0.05</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;0.05</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">ICIR</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;0.3</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.3-0.5</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.5-1.0</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;1.0</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">{t("Hit Rate", "命中率")}</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;50%</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">50-55%</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">55-65%</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;65%</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">L/S Sharpe</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;0.3</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.3-0.5</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.5-1.0</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;1.0</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">{t("Monotonicity", "單調性")}</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;0.3</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.3-0.5</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.5-0.8</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;0.8</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4 font-medium">{t("Turnover", "周轉率")}</td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&gt;80%</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">50-80%</span></td>
              <td className="py-2 pr-4"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">20-50%</span></td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">&lt;20%</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Tip: Don't chase high IC alone. A factor with moderate IC but high ICIR and good monotonicity is much more tradeable than a high-IC factor with poor consistency. Consistency is king.",
          "提示：不要只追求高 IC。一個 IC 中等但 ICIR 高、單調性好的因子，比一個 IC 高但一致性差的因子更適合交易。一致性才是王道。",
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  alpha-walkthrough                                                 */
/* ------------------------------------------------------------------ */
function AlphaWalkthroughSection({ t }: { t: T }) {
  const steps = [
    {
      numEn: "Step 1",
      numZh: "步驟 1",
      titleEn: "Navigate to the Research Page",
      titleZh: "前往研究頁面",
      descEn: "Open the Research page from the sidebar navigation, then click the \"Alpha Research\" tab. This is where all factor analysis happens.",
      descZh: "從側邊欄導航打開研究頁面，然後點擊「Alpha 研究」分頁。所有因子分析都在這裡進行。",
    },
    {
      numEn: "Step 2",
      numZh: "步驟 2",
      titleEn: "Select Your Factors",
      titleZh: "選擇你的因子",
      descEn: "Open the \"Factors\" panel. For your first research, select Momentum (with UP direction) and Mean Reversion (with DOWN direction). The direction arrow indicates whether higher or lower values are better.",
      descZh: "打開「因子」面板。第一次研究建議選擇動量（方向朝上）和均值回歸（方向朝下）。方向箭頭表示值越高還是越低越好。",
    },
    {
      numEn: "Step 3",
      numZh: "步驟 3",
      titleEn: "Choose Your Stock Universe",
      titleZh: "選擇股票池",
      descEn: "Open the stock universe picker. Select a preset like \"台股 50\" (top 50 Taiwan stocks) or \"S&P 500\" for US stocks. Start with a smaller universe for faster results.",
      descZh: "打開股票池選擇器。選擇一個預設如「台股 50」（台灣前 50 大股票）或「S&P 500」。從較小的股票池開始，可以更快得到結果。",
    },
    {
      numEn: "Step 4",
      numZh: "步驟 4",
      titleEn: "Set Date Range",
      titleZh: "設定日期範圍",
      descEn: "Set the start date to 2020-01-01 and the end date to today. This gives you 5+ years of data covering COVID crash, recovery, and various market regimes.",
      descZh: "將開始日期設為 2020-01-01，結束日期設為今天。這提供 5 年以上的數據，涵蓋 COVID 崩盤、復甦和各種市場狀態。",
    },
    {
      numEn: "Step 5",
      numZh: "步驟 5",
      titleEn: "Configure Neutralization",
      titleZh: "設定中性化",
      descEn: "Set neutralization to \"Market\" (removes market-wide effects so you're measuring pure stock selection skill). This ensures your factor isn't just picking up whether the market is going up or down.",
      descZh: "將中性化設為「Market」（移除市場整體效應，這樣你衡量的是純粹的選股能力）。這確保你的因子不只是在捕捉市場漲跌。",
    },
    {
      numEn: "Step 6",
      numZh: "步驟 6",
      titleEn: "Set Quantiles",
      titleZh: "設定分位數",
      descEn: "Set quantiles to 5. This divides your stock universe into 5 groups (Q1=worst to Q5=best) based on factor scores. 5 quantiles provides good granularity without requiring a huge universe.",
      descZh: "將分位數設為 5。這會根據因子分數將你的股票池分成 5 組（Q1=最差到 Q5=最好）。5 個分位提供良好的細粒度，又不需要龐大的股票池。",
    },
    {
      numEn: "Step 7",
      numZh: "步驟 7",
      titleEn: "Run the Analysis",
      titleZh: "執行分析",
      descEn: "Click \"Run Analysis\" and wait. The progress bar shows data download and computation progress. First run may take a few minutes as data is being downloaded and cached.",
      descZh: "點擊「執行分析」然後等待。進度條顯示數據下載和計算進度。首次運行可能需要幾分鐘，因為數據正在下載和快取。",
    },
    {
      numEn: "Step 8",
      numZh: "步驟 8",
      titleEn: "Check the Factor Summary Table",
      titleZh: "檢查因子摘要表",
      descEn: "Look at the Factor Summary table. The key numbers to check first: IC Mean (want > 0.03), ICIR (want > 0.5), and Hit Rate (want > 55%). If these look good, the factor has predictive power.",
      descZh: "查看因子摘要表。首先要檢查的關鍵數字：IC 平均值（希望 > 0.03）、ICIR（希望 > 0.5）和命中率（希望 > 55%）。如果這些看起來不錯，因子就有預測力。",
    },
    {
      numEn: "Step 9",
      numZh: "步驟 9",
      titleEn: "Explore the Details",
      titleZh: "探索細節",
      descEn: "Click a factor row to see the IC time series chart (is it stable or erratic?) and the quantile return chart (does Q5 consistently beat Q1?). A good factor shows stable positive IC and smooth quantile ordering.",
      descZh: "點擊因子行查看 IC 時間序列圖（是穩定還是不規則？）和分位報酬圖（Q5 是否持續打敗 Q1？）。好的因子顯示穩定的正 IC 和平滑的分位排序。",
    },
    {
      numEn: "Step 10",
      numZh: "步驟 10",
      titleEn: "Evaluate the Composite Alpha",
      titleZh: "評估複合 Alpha",
      descEn: "Check the composite alpha (the combined signal from all selected factors). If it has positive IC and the quantile chart shows Q5 > Q1, your combination works! The composite should be better than individual factors — that's the power of diversification.",
      descZh: "檢查複合 alpha（所有選定因子的組合信號）。如果它有正的 IC 且分位圖顯示 Q5 > Q1，你的組合有效！複合信號應該比個別因子更好 — 這就是分散化的力量。",
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Walkthrough: Your First Alpha Research", "實作：第一次 Alpha 研究")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Follow these steps to run your first factor research analysis. By the end, you'll know whether your chosen factors have real predictive power in your target market.",
          "按照以下步驟執行你的第一次因子研究分析。完成後，你就會知道你選擇的因子在目標市場中是否有真正的預測力。",
        )}
      </p>

      {steps.map((step, idx) => (
        <div key={idx} className="flex items-start gap-3 mb-4">
          <div className="bg-blue-500 text-white rounded-full w-7 h-7 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5">
            {idx + 1}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1">
              {t(step.titleEn, step.titleZh)}
            </h3>
            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              {t(step.descEn, step.descZh)}
            </p>
          </div>
        </div>
      ))}

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Next Step", "下一步")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "If your factor combination looks promising (positive IC, good ICIR, smooth quantile returns), the next step is to take it to backtesting. The backtest will show you the full historical performance including returns, drawdowns, and transaction costs.",
          "如果你的因子組合看起來有前景（正的 IC、好的 ICIR、平滑的分位報酬），下一步是進入回測。回測會顯示完整的歷史表現，包括報酬、回撤和交易成本。",
        )}
      </p>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t("Ready to run your first research? Go to the ", "準備好執行第一次研究了嗎？前往")}
        <Link to="/research" className="text-blue-600 dark:text-blue-400 underline underline-offset-2">
          {t("Research page", "研究頁面")}
        </Link>
        {t(" and follow the steps above.", "，按照上述步驟操作。")}
      </div>
    </div>
  );
}
