import { useT } from "@core/i18n";
import { Link } from "react-router-dom";

export function ChapterOverview({ section }: { section?: string }) {
  const { lang } = useT();
  const t = (en: string, zh: string) => (lang === "zh" ? zh : en);

  if (section === "workflow") return <WorkflowSection t={t} />;
  if (section === "who-is-it-for") return <WhoIsItForSection t={t} />;
  return <WhatIsThisSection t={t} />;
}

type T = (en: string, zh: string) => string;

/* ------------------------------------------------------------------ */
/*  what-is-this                                                      */
/* ------------------------------------------------------------------ */
function WhatIsThisSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("What This System Does", "這個系統能做什麼")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "This is a quantitative trading research and execution platform designed for individual investors and family offices. It helps you make investment decisions backed by data and systematic analysis, rather than gut feeling or tips from friends.",
          "這是一個量化交易研究與執行平台，專為個人投資者與家族辦公室設計。它幫助你根據數據和系統化分析做出投資決策，而不是憑直覺或聽朋友的推薦。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Full Investment Cycle", "完整投資週期")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The platform covers the entire cycle of quantitative investing:",
          "平台涵蓋量化投資的完整週期：",
        )}
      </p>

      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>
          <strong>{t("Research", "研究")}</strong> {t("— discover which factors predict stock returns", "— 探索哪些因子能預測股票報酬")}
        </li>
        <li>
          <strong>{t("Backtest", "回測")}</strong> {t("— test strategies on years of historical data", "— 在多年歷史數據上測試策略")}
        </li>
        <li>
          <strong>{t("Paper Trading", "模擬交易")}</strong> {t("— run strategies in real-time without risking real money", "— 用即時市場資料執行策略，不用冒真金白銀的風險")}
        </li>
        <li>
          <strong>{t("Live Trading", "實盤交易")}</strong> {t("— connect to a broker and execute real trades", "— 連接券商，執行真實交易")}
        </li>
      </ul>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Market Coverage", "市場覆蓋")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "The system supports multiple asset classes across different markets:",
          "系統支援不同市場的多種資產類別：",
        )}
      </p>

      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Taiwan stocks (TWSE/TPEx)", "台灣股票 (上市/上櫃)")}</li>
        <li>{t("US stocks (NYSE, NASDAQ)", "美國股票 (NYSE, NASDAQ)")}</li>
        <li>{t("ETFs — including bond and commodity ETF proxies", "ETF — 包括債券和商品 ETF 替代品")}</li>
        <li>{t("Futures (Taiwan & US)", "期貨 (台灣與美國)")}</li>
      </ul>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Taiwan Market Defaults", "台灣市場預設值")}
      </h2>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Default settings are optimized for the Taiwan stock market, so you can start without worrying about configuration:",
          "預設設定已針對台灣股市優化，你可以直接開始使用，不用擔心設定問題：",
        )}
      </p>

      <div className="overflow-x-auto mb-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-surface-light">
              <th className="text-left py-2 pr-4 text-slate-700 dark:text-slate-300">{t("Setting", "設定")}</th>
              <th className="text-left py-2 text-slate-700 dark:text-slate-300">{t("Default Value", "預設值")}</th>
            </tr>
          </thead>
          <tbody className="text-slate-600 dark:text-slate-400">
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4">{t("Commission Rate", "手續費率")}</td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.1425%</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4">{t("Sell Tax", "交易稅")}</td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">0.3%</span></td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-surface-light">
              <td className="py-2 pr-4">{t("Slippage", "滑價")}</td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">5 bps (0.05%)</span></td>
            </tr>
            <tr>
              <td className="py-2 pr-4">{t("Lot Size", "交易單位")}</td>
              <td className="py-2"><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">1000 {t("shares", "股")}</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Tip: These defaults work for most Taiwan stock investors. If you trade US stocks, the system will automatically use the correct fee structure for your chosen market.",
          "提示：這些預設值適合大部分台灣股票投資者。如果你交易美國股票，系統會自動使用你所選市場的正確費率結構。",
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  workflow                                                          */
/* ------------------------------------------------------------------ */
function WorkflowSection({ t }: { t: T }) {
  const steps = [
    {
      num: 1,
      titleEn: "Research",
      titleZh: "研究",
      color: "bg-blue-500",
      descEn:
        "Use factor models to find stock characteristics that predict returns. The core question: \"Which factors actually work in this market?\" This step matters because without rigorous research, you're just guessing. Factor analysis lets you discover persistent patterns — like momentum or value — that have economic explanations for why they generate excess returns. Skipping this step is the #1 reason retail strategies fail.",
      descZh:
        "使用因子模型尋找能預測報酬的股票特徵。核心問題：「哪些因子在這個市場真正有效？」這個步驟很重要，因為沒有嚴謹的研究，你只是在猜測。因子分析讓你發現持續存在的規律 — 例如動量或價值 — 這些規律有其經濟學解釋。跳過這一步是散戶策略失敗的首要原因。",
    },
    {
      num: 2,
      titleEn: "Backtest",
      titleZh: "回測",
      color: "bg-green-500",
      descEn:
        "Test your strategy on 5+ years of historical data. The core question: \"Would this strategy have made money in the past?\" Backtesting reveals whether your research insights translate into actual returns after accounting for trading costs, slippage, and realistic constraints. A strategy that looks great on paper but fails in backtest is a strategy you should NOT trade. This step also helps you calibrate expectations for risk and drawdowns.",
      descZh:
        "在 5 年以上的歷史資料上測試你的策略。核心問題：「這個策略在過去是否能賺錢？」回測能揭示你的研究洞見在扣除交易成本、滑價和現實限制後，是否還能產生實際報酬。一個在紙上看起來很棒但回測失敗的策略，你就不應該交易它。這一步也幫助你校準對風險和回撤的預期。",
    },
    {
      num: 3,
      titleEn: "Paper Trading",
      titleZh: "模擬交易",
      color: "bg-amber-500",
      descEn:
        "Run the strategy with real-time market data but no real money. The core question: \"Does it work in real-time, not just in hindsight?\" Paper trading catches problems that backtests miss: execution timing, data delays, market microstructure effects, and your own psychological reactions to watching the strategy trade. It's the bridge between historical analysis and live execution. Most strategies need 1-3 months of paper trading before going live.",
      descZh:
        "用即時市場資料執行策略，但不使用真金白銀。核心問題：「它在即時環境中有效，還是只是事後諸葛亮？」模擬交易能抓到回測遺漏的問題：執行時機、資料延遲、市場微結構效應，以及你自己看著策略交易時的心理反應。它是歷史分析和實盤執行之間的橋梁。大多數策略在上線前需要 1-3 個月的模擬交易。",
    },
    {
      num: 4,
      titleEn: "Live Trading",
      titleZh: "實盤交易",
      color: "bg-red-500",
      descEn:
        "Connect to a broker and execute real trades. The core question: \"Ready to go live with confidence.\" After passing research, backtest, and paper trading, you have statistical evidence that your strategy works. Live trading adds real economic risk, but you enter it with a clear understanding of expected returns, maximum drawdown, and when to pull the plug. Discipline comes from data, not emotion.",
      descZh:
        "連接券商，執行真實交易。核心問題：「準備好帶著信心上線了。」經過研究、回測和模擬交易後，你有統計證據證明策略有效。實盤交易增加了真實的經濟風險，但你帶著對預期報酬、最大回撤以及何時停損的清晰理解進入市場。紀律來自數據，而非情緒。",
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Core Workflow", "核心工作流程")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "Every successful quantitative strategy follows the same four-step process. Skipping steps is the most common mistake — each step exists to catch failures before they cost you real money.",
          "每個成功的量化策略都遵循相同的四步流程。跳過步驟是最常見的錯誤 — 每一步的存在都是為了在真正虧錢之前發現問題。",
        )}
      </p>

      <div className="flex flex-col gap-2 mb-6">
        {steps.map((step, idx) => (
          <div key={step.num}>
            <div className="flex items-start gap-4 p-4 rounded-lg border border-slate-200 dark:border-surface-light bg-slate-50 dark:bg-surface-dark">
              <div className={`${step.color} text-white rounded-full w-8 h-8 flex items-center justify-center shrink-0 font-bold text-sm`}>
                {step.num}
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-1">
                  {t(step.titleEn, step.titleZh)}
                </h3>
                <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  {t(step.descEn, step.descZh)}
                </p>
              </div>
            </div>
            {idx < steps.length - 1 && (
              <div className="flex justify-center py-1">
                <svg width="20" height="20" viewBox="0 0 20 20" className="text-slate-400 dark:text-slate-500">
                  <path d="M10 4 L10 14 M6 10 L10 14 L14 10" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Tip: Don't rush to live trading. Most professional quant funds spend 80% of their time on research and backtesting. The money is made in the preparation, not the execution.",
          "提示：不要急著上線交易。大多數專業量化基金把 80% 的時間花在研究和回測上。錢是在準備階段賺到的，不是在執行階段。",
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  who-is-it-for                                                     */
/* ------------------------------------------------------------------ */
function WhoIsItForSection({ t }: { t: T }) {
  return (
    <div>
      <h1 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
        {t("Who Is This For?", "適合誰使用？")}
      </h1>

      <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
        {t(
          "This platform is designed for people who want to take a systematic, data-driven approach to investing. You don't need to be a finance PhD, but you should be comfortable with numbers and willing to learn.",
          "這個平台是為想要以系統化、數據驅動方式進行投資的人設計的。你不需要是金融博士，但你應該對數字感到自在，並且願意學習。",
        )}
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Ideal Users", "理想使用者")}
      </h2>

      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>
          <strong>{t("Individual investors", "個人投資者")}</strong>{" "}
          {t(
            "who want systematic, emotion-free investing. If you've ever panic-sold at the bottom or FOMO-bought at the top, systematic strategies can remove that human weakness.",
            "想要系統化、無情緒的投資。如果你曾在底部恐慌賣出或在頂部追高買入，系統化策略可以消除這種人性弱點。",
          )}
        </li>
        <li>
          <strong>{t("Math / engineering backgrounds", "數學／工程背景")}</strong>{" "}
          {t(
            "who want to apply quantitative methods to investing. Your analytical skills transfer directly to factor research and portfolio optimization.",
            "想將量化方法應用於投資。你的分析技能可以直接轉移到因子研究和投資組合優化。",
          )}
        </li>
        <li>
          <strong>{t("Family offices", "家族辦公室")}</strong>{" "}
          {t(
            "managing multi-asset portfolios across stocks, bonds (via ETFs), and futures. The asset allocation and risk management tools are built for this use case.",
            "管理跨股票、債券（透過 ETF）和期貨的多資產投資組合。資產配置和風險管理工具就是為這種使用情境打造的。",
          )}
        </li>
        <li>
          <strong>{t("Frustrated traders", "受挫的交易者")}</strong>{" "}
          {t(
            "who are tired of \"gut feeling\" trading and want data-backed decisions. If you've tried technical analysis or stock picking and felt like it was more art than science, this platform provides the science.",
            "厭倦了憑「直覺」交易，想要有數據支持的決策。如果你試過技術分析或選股，覺得它更像藝術而非科學，這個平台提供的就是科學。",
          )}
        </li>
      </ul>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Important: This Is NOT a Black-Box Trading Bot", "重要：這不是黑箱交易機器人")}
      </h2>

      <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
        {t(
          "This platform is a tool, not an autopilot. You need to understand what your strategy does, why it works, and when it might fail. The system provides the analytical framework and execution infrastructure — but the investment decisions are yours. Don't trade a strategy you don't understand.",
          "這個平台是工具，不是自動駕駛。你需要了解你的策略做了什麼、為什麼有效、什麼時候可能失敗。系統提供分析框架和執行基礎設施 — 但投資決策是你自己的。不要交易你不理解的策略。",
        )}
      </div>

      <h2 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
        {t("Prerequisites", "先備知識")}
      </h2>

      <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
        <li>{t("Basic understanding of stock markets (what stocks, ETFs, and futures are)", "對股票市場的基本了解（什麼是股票、ETF 和期貨）")}</li>
        <li>{t("Comfort with numbers and basic statistics (mean, standard deviation, correlation)", "對數字和基本統計的熟悉（平均值、標準差、相關性）")}</li>
        <li>{t("Patience to go through the research → backtest → paper trade workflow", "耐心走完 研究 → 回測 → 模擬交易 的流程")}</li>
        <li>{t("NO programming required — everything is done through the web interface", "不需要程式設計 — 一切都透過網頁介面完成")}</li>
      </ul>

      <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
        {t(
          "Tip: If you're new to quantitative investing, start with the Alpha Research chapter to learn about factors, then move to Backtesting. Take it one step at a time.",
          "提示：如果你是量化投資新手，從 Alpha 研究章節開始學習因子，然後進入回測。一步一步來。",
        )}
      </div>
    </div>
  );
}
