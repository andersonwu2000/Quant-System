import { Link } from "react-router-dom";
import {
  BookOpen,
  FlaskConical,
  Microscope,
  PlayCircle,
  ShieldAlert,
  ArrowRight,
  Lightbulb,
  TrendingUp,
  BarChart3,
  Activity,
  Layers,
  Target,
  PieChart,
  Sparkles,
} from "lucide-react";
import { Card } from "@shared/ui";
import { useT } from "@core/i18n";
import type { Lang } from "@core/i18n";

type Bilingual = { en: string; zh: string };

const pick = (b: Bilingual, lang: Lang) => (lang === "zh" ? b.zh : b.en);

/* ─── Section 1: What is this system? ─── */
const systemSummary: Bilingual = {
  en: "A quantitative trading research platform for individual investors and family asset management. It helps you make investment decisions backed by data and systematic analysis instead of gut feelings.",
  zh: "一個為個人投資者與家庭資產管理設計的量化交易研究平台。幫助你用數據與系統化分析做出投資決策，而非依賴直覺。",
};

const whoItsFor: Bilingual = {
  en: "Designed for investors who want to take a data-driven approach: test ideas before risking real capital, manage risk with clear rules, and build a repeatable process.",
  zh: "專為想要採用數據驅動方法的投資人設計：在投入真金白銀之前先測試想法，用明確規則管理風險，建立可重複的投資流程。",
};

/* ─── Section 2: Core Workflow ─── */
const workflowSteps: { icon: typeof Microscope; label: Bilingual; desc: Bilingual }[] = [
  {
    icon: Microscope,
    label: { en: "Research", zh: "研究" },
    desc: {
      en: "Discover which stock characteristics (factors) predict future returns. Analyze data to find patterns that give you an edge.",
      zh: "探索哪些股票特徵（因子）能預測未來收益。分析數據，找出能帶來優勢的規律。",
    },
  },
  {
    icon: FlaskConical,
    label: { en: "Backtest", zh: "回測" },
    desc: {
      en: "Test your strategy on years of historical data. See how it would have performed before risking any money.",
      zh: "用多年的歷史數據測試你的策略。在投入任何資金之前，看看它的表現如何。",
    },
  },
  {
    icon: PlayCircle,
    label: { en: "Paper Trade", zh: "模擬交易" },
    desc: {
      en: "Run your strategy with live market data but no real money. Validate that it works in real-time conditions.",
      zh: "使用即時市場數據但不投入真金白銀來運行你的策略。驗證它在真實條件下是否有效。",
    },
  },
  {
    icon: TrendingUp,
    label: { en: "Live", zh: "實盤" },
    desc: {
      en: "Deploy your validated strategy with real capital. The system monitors risk and executes trades automatically.",
      zh: "以真實資金部署經過驗證的策略。系統自動監控風險並執行交易。",
    },
  },
];

/* ─── Section 3: Getting Started Steps ─── */
const gettingStartedSteps: {
  icon: typeof Microscope;
  title: Bilingual;
  desc: Bilingual;
  link: string;
  linkLabel: Bilingual;
}[] = [
  {
    icon: Microscope,
    title: { en: "Step 1: Alpha Research", zh: "步驟一：Alpha 研究" },
    desc: {
      en: "Pick factors (stock characteristics like momentum or value) and analyze which ones predict future returns. The system computes statistics to tell you if a factor is worth using. Think of it as testing whether your investment hypothesis holds up.",
      zh: "選擇因子（如動量、價值等股票特徵），分析哪些能預測未來收益。系統會計算統計數據，告訴你某個因子是否值得使用。可以把它想成在測試你的投資假說是否成立。",
    },
    link: "/research",
    linkLabel: { en: "Go to Alpha Research", zh: "前往 Alpha 研究" },
  },
  {
    icon: FlaskConical,
    title: { en: "Step 2: Backtest", zh: "步驟二：回測" },
    desc: {
      en: "Once you have a strategy idea, test it on historical data. The backtest engine simulates real trading conditions — including commissions, slippage, and tax — so the results are realistic. Look for strategies with a Sharpe ratio above 1.0 and reasonable drawdowns.",
      zh: "有了策略想法後，用歷史數據測試它。回測引擎模擬真實交易條件 — 包含手續費、滑價和稅 — 讓結果更貼近現實。尋找夏普比率高於 1.0 且回撤合理的策略。",
    },
    link: "/research",
    linkLabel: { en: "Go to Backtest", zh: "前往回測" },
  },
  {
    icon: PlayCircle,
    title: { en: "Step 3: Paper Trading", zh: "步驟三：模擬交易" },
    desc: {
      en: "Before using real money, run your strategy in paper trading mode. It uses live market data but only simulates trades. This step catches issues that backtesting might miss, like data delays or unusual market conditions.",
      zh: "在使用真金白銀之前，先用模擬交易模式運行你的策略。它使用即時市場數據，但只模擬交易。這一步能發現回測可能遺漏的問題，例如數據延遲或異常市場狀況。",
    },
    link: "/trading",
    linkLabel: { en: "Go to Trading", zh: "前往交易" },
  },
  {
    icon: ShieldAlert,
    title: { en: "Step 4: Risk Management", zh: "步驟四：風險管理" },
    desc: {
      en: "Set guardrails to protect your capital. Configure maximum position sizes, daily loss limits, and the kill switch (emergency stop). Good risk management is what keeps you in the game long-term.",
      zh: "設定護欄保護你的資金。配置最大持倉比例、每日虧損上限和緊急停止開關。良好的風險管理是長期生存的關鍵。",
    },
    link: "/risk",
    linkLabel: { en: "Go to Risk Management", zh: "前往風險管理" },
  },
];

/* ─── Section 4: Key Concepts ─── */
const concepts: { icon: typeof Lightbulb; title: Bilingual; desc: Bilingual }[] = [
  {
    icon: Layers,
    title: { en: "Factor", zh: "因子 (Factor)" },
    desc: {
      en: "A measurable characteristic of stocks (like momentum or value) that might predict returns. Think of it as a \"recipe ingredient\" for your investment strategy. Different factors capture different market behaviors.",
      zh: "股票的可量化特徵（如動量或價值），可能用來預測收益。把它想成投資策略的「配方原料」。不同因子捕捉不同的市場行為。",
    },
  },
  {
    icon: Target,
    title: { en: "IC / ICIR", zh: "IC / ICIR" },
    desc: {
      en: "IC measures how well a factor predicts returns, ranging from -1 to 1. ICIR measures the consistency of that prediction. A factor with IC > 0.03 and ICIR > 0.5 is worth investigating further.",
      zh: "IC 衡量因子預測收益的能力，範圍 -1 到 1。ICIR 衡量預測的穩定性。IC > 0.03 且 ICIR > 0.5 的因子值得進一步研究。",
    },
  },
  {
    icon: BarChart3,
    title: { en: "Sharpe Ratio", zh: "夏普比率 (Sharpe Ratio)" },
    desc: {
      en: "Return per unit of risk. Above 1.0 is good, above 2.0 is excellent. It lets you compare strategies fairly regardless of how aggressive they are — higher Sharpe means better risk-adjusted performance.",
      zh: "每單位風險所獲得的收益。超過 1.0 為佳，超過 2.0 為優異。無論策略多激進，都能公平比較 — 夏普越高，風險調整後的表現越好。",
    },
  },
  {
    icon: Activity,
    title: { en: "Drawdown", zh: "回撤 (Drawdown)" },
    desc: {
      en: "The biggest drop from peak to trough in your portfolio value. If max drawdown is -20%, at the worst point you'd have lost 20% from your highest balance. This is key for setting your risk tolerance.",
      zh: "投資組合從峰值到谷底的最大跌幅。如果最大回撤為 -20%，表示在最糟的時候你會從最高餘額虧損 20%。這是設定風險承受度的關鍵指標。",
    },
  },
  {
    icon: Sparkles,
    title: { en: "Neutralization", zh: "中性化 (Neutralization)" },
    desc: {
      en: "Removing market or industry biases from factor scores so you're measuring pure stock-specific signals, not just \"the market went up.\" It's like controlling for confounding variables in an experiment.",
      zh: "從因子分數中移除市場或行業偏差，讓你衡量的是純粹的個股信號，而不只是「大盤漲了」。就像在實驗中控制干擾變數一樣。",
    },
  },
  {
    icon: PieChart,
    title: { en: "Quantile Returns", zh: "分位數收益 (Quantile Returns)" },
    desc: {
      en: "Sort stocks by factor score into groups (e.g., 5 groups). If the top group consistently beats the bottom group, the factor works. The bigger the spread, the more powerful the signal.",
      zh: "按因子分數將股票排序分組（例如 5 組）。如果頂部組持續勝過底部組，表示因子有效。差距越大，信號越強。",
    },
  },
];

/* ─── Section Titles ─── */
const sectionTitles = {
  whatIsThis: { en: "What is this system?", zh: "這個系統是什麼？" },
  coreWorkflow: { en: "Core Workflow", zh: "核心流程" },
  gettingStarted: { en: "Getting Started", zh: "開始使用" },
  keyConcepts: { en: "Key Concepts Quick Reference", zh: "關鍵概念速覽" },
};

export function GettingStarted() {
  const { lang } = useT();

  return (
    <div className="space-y-6">
      {/* Section 1: What is this system? */}
      <Card className="p-5">
        <div className="flex items-start gap-3 mb-3">
          <BookOpen size={20} className="text-blue-500 mt-0.5 shrink-0" />
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
            {pick(sectionTitles.whatIsThis, lang)}
          </h3>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed mb-2">
          {pick(systemSummary, lang)}
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-500 leading-relaxed">
          {pick(whoItsFor, lang)}
        </p>
      </Card>

      {/* Section 2: Core Workflow */}
      <Card className="p-5">
        <div className="flex items-start gap-3 mb-4">
          <Lightbulb size={20} className="text-amber-500 mt-0.5 shrink-0" />
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
            {pick(sectionTitles.coreWorkflow, lang)}
          </h3>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch gap-2 sm:gap-0">
          {workflowSteps.map((step, i) => {
            const Icon = step.icon;
            return (
              <div key={i} className="flex items-center flex-1 min-w-0">
                <div className="flex-1 bg-slate-100 dark:bg-surface-dark rounded-lg p-3 text-center">
                  <Icon size={24} className="mx-auto text-blue-500 mb-1.5" />
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    {pick(step.label, lang)}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-500 leading-relaxed">
                    {pick(step.desc, lang)}
                  </p>
                </div>
                {i < workflowSteps.length - 1 && (
                  <ArrowRight
                    size={16}
                    className="text-slate-400 shrink-0 mx-1 hidden sm:block"
                  />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Section 3: Getting Started Steps */}
      <Card className="p-5">
        <div className="flex items-start gap-3 mb-4">
          <BookOpen size={20} className="text-emerald-500 mt-0.5 shrink-0" />
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
            {pick(sectionTitles.gettingStarted, lang)}
          </h3>
        </div>
        <div className="space-y-4">
          {gettingStartedSteps.map((step, i) => {
            const Icon = step.icon;
            return (
              <div
                key={i}
                className="flex items-start gap-3 bg-slate-50 dark:bg-surface-dark rounded-lg p-4"
              >
                <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Icon size={16} className="text-blue-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    {pick(step.title, lang)}
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-500 leading-relaxed mb-2">
                    {pick(step.desc, lang)}
                  </p>
                  <Link
                    to={step.link}
                    className="inline-flex items-center gap-1 text-xs text-blue-500 hover:text-blue-400 font-medium transition-colors"
                  >
                    {pick(step.linkLabel, lang)}
                    <ArrowRight size={12} />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Section 4: Key Concepts */}
      <Card className="p-5">
        <div className="flex items-start gap-3 mb-4">
          <Lightbulb size={20} className="text-purple-500 mt-0.5 shrink-0" />
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
            {pick(sectionTitles.keyConcepts, lang)}
          </h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {concepts.map((concept, i) => {
            const Icon = concept.icon;
            return (
              <div
                key={i}
                className="bg-slate-50 dark:bg-surface-dark rounded-lg p-3"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <Icon size={14} className="text-purple-500 shrink-0" />
                  <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {pick(concept.title, lang)}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-500 leading-relaxed">
                  {pick(concept.desc, lang)}
                </p>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
