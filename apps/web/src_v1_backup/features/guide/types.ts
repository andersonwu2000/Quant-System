export interface Section {
  id: string;
  titleEn: string;
  titleZh: string;
}

export interface Chapter {
  id: string;
  titleEn: string;
  titleZh: string;
  sections: Section[];
}

export const TOC: Chapter[] = [
  {
    id: "overview",
    titleEn: "System Overview",
    titleZh: "系統概述",
    sections: [
      { id: "what-is-this", titleEn: "What This System Does", titleZh: "這個系統能做什麼" },
      { id: "workflow", titleEn: "Core Workflow", titleZh: "核心工作流程" },
      { id: "who-is-it-for", titleEn: "Who Is It For", titleZh: "適合誰使用" },
    ],
  },
  {
    id: "alpha",
    titleEn: "Alpha Research",
    titleZh: "Alpha 研究教學",
    sections: [
      { id: "what-are-factors", titleEn: "What Are Factors?", titleZh: "什麼是因子？" },
      { id: "factor-catalog", titleEn: "Factor Catalog", titleZh: "因子詳解" },
      { id: "choosing-factors", titleEn: "Choosing Factor Combinations", titleZh: "如何選擇因子組合" },
      { id: "reading-results", titleEn: "Reading Research Results", titleZh: "讀懂研究結果" },
      { id: "alpha-walkthrough", titleEn: "Walkthrough: Your First Research", titleZh: "實作：第一次因子研究" },
    ],
  },
  {
    id: "backtest",
    titleEn: "Backtesting",
    titleZh: "回測教學",
    sections: [
      { id: "what-is-backtest", titleEn: "What Is Backtesting?", titleZh: "什麼是回測？" },
      { id: "params-guide", titleEn: "Parameter Guide", titleZh: "參數設定指南" },
      { id: "reading-report", titleEn: "Reading Backtest Reports", titleZh: "讀懂回測報告" },
      { id: "common-pitfalls", titleEn: "Common Pitfalls", titleZh: "常見陷阱" },
    ],
  },
  {
    id: "allocation",
    titleEn: "Asset Allocation",
    titleZh: "資產配置教學",
    sections: [
      { id: "strategic-vs-tactical", titleEn: "Strategic vs Tactical", titleZh: "戰略配置 vs 戰術配置" },
      { id: "macro-regime", titleEn: "Macro Factors & Market Regime", titleZh: "宏觀因子與市場狀態" },
      { id: "optimizers", titleEn: "Risk Parity & Black-Litterman", titleZh: "Risk Parity 與 Black-Litterman" },
    ],
  },
  {
    id: "paper-trading",
    titleEn: "Paper Trading",
    titleZh: "模擬交易教學",
    sections: [
      { id: "research-to-trade", titleEn: "From Research to Trading", titleZh: "從研究到實戰" },
      { id: "broker-setup", titleEn: "Broker Connection (Shioaji)", titleZh: "連接券商（Shioaji）" },
      { id: "monitoring", titleEn: "Monitoring & Reconciliation", titleZh: "監控與對帳" },
    ],
  },
  {
    id: "risk",
    titleEn: "Risk Management",
    titleZh: "風險管理教學",
    sections: [
      { id: "why-risk-rules", titleEn: "Why Risk Rules Matter", titleZh: "為什麼需要風控規則" },
      { id: "rules-explained", titleEn: "Rules Explained", titleZh: "各規則詳解" },
      { id: "kill-switch", titleEn: "Kill Switch", titleZh: "Kill Switch 機制" },
    ],
  },
  {
    id: "faq",
    titleEn: "FAQ",
    titleZh: "常見問題",
    sections: [
      { id: "faq-general", titleEn: "General Questions", titleZh: "一般問題" },
      { id: "faq-data", titleEn: "Data & Market Coverage", titleZh: "數據與市場覆蓋" },
      { id: "faq-troubleshooting", titleEn: "Troubleshooting", titleZh: "問題排解" },
    ],
  },
];
