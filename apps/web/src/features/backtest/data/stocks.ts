export interface StockEntry {
  ticker: string;
  name: string;
  market: "US" | "TW" | "ETF";
  sector?: string;
}

// ── 美股 (S&P 500 精選 ~100) ──────────────────────────────────

const US_STOCKS: StockEntry[] = [
  // Technology
  { ticker: "AAPL", name: "Apple", market: "US", sector: "Technology" },
  { ticker: "MSFT", name: "Microsoft", market: "US", sector: "Technology" },
  { ticker: "GOOGL", name: "Alphabet (A)", market: "US", sector: "Technology" },
  { ticker: "GOOG", name: "Alphabet (C)", market: "US", sector: "Technology" },
  { ticker: "META", name: "Meta Platforms", market: "US", sector: "Technology" },
  { ticker: "NVDA", name: "NVIDIA", market: "US", sector: "Technology" },
  { ticker: "AMZN", name: "Amazon", market: "US", sector: "Technology" },
  { ticker: "TSLA", name: "Tesla", market: "US", sector: "Technology" },
  { ticker: "CRM", name: "Salesforce", market: "US", sector: "Technology" },
  { ticker: "CSCO", name: "Cisco Systems", market: "US", sector: "Technology" },
  { ticker: "INTC", name: "Intel", market: "US", sector: "Technology" },
  { ticker: "IBM", name: "IBM", market: "US", sector: "Technology" },
  { ticker: "ORCL", name: "Oracle", market: "US", sector: "Technology" },
  { ticker: "QCOM", name: "Qualcomm", market: "US", sector: "Technology" },
  { ticker: "TXN", name: "Texas Instruments", market: "US", sector: "Technology" },
  { ticker: "PYPL", name: "PayPal", market: "US", sector: "Technology" },
  { ticker: "ADBE", name: "Adobe", market: "US", sector: "Technology" },
  { ticker: "AVGO", name: "Broadcom", market: "US", sector: "Technology" },
  { ticker: "AMD", name: "AMD", market: "US", sector: "Technology" },
  { ticker: "NFLX", name: "Netflix", market: "US", sector: "Technology" },
  { ticker: "UBER", name: "Uber", market: "US", sector: "Technology" },
  { ticker: "NOW", name: "ServiceNow", market: "US", sector: "Technology" },
  { ticker: "SHOP", name: "Shopify", market: "US", sector: "Technology" },
  { ticker: "SQ", name: "Block (Square)", market: "US", sector: "Technology" },
  { ticker: "SNOW", name: "Snowflake", market: "US", sector: "Technology" },
  { ticker: "PLTR", name: "Palantir", market: "US", sector: "Technology" },
  { ticker: "MU", name: "Micron Technology", market: "US", sector: "Technology" },
  { ticker: "AMAT", name: "Applied Materials", market: "US", sector: "Technology" },
  { ticker: "LRCX", name: "Lam Research", market: "US", sector: "Technology" },
  { ticker: "KLAC", name: "KLA Corp", market: "US", sector: "Technology" },
  // Finance
  { ticker: "JPM", name: "JPMorgan Chase", market: "US", sector: "Finance" },
  { ticker: "BAC", name: "Bank of America", market: "US", sector: "Finance" },
  { ticker: "WFC", name: "Wells Fargo", market: "US", sector: "Finance" },
  { ticker: "GS", name: "Goldman Sachs", market: "US", sector: "Finance" },
  { ticker: "MS", name: "Morgan Stanley", market: "US", sector: "Finance" },
  { ticker: "C", name: "Citigroup", market: "US", sector: "Finance" },
  { ticker: "BLK", name: "BlackRock", market: "US", sector: "Finance" },
  { ticker: "BK", name: "BNY Mellon", market: "US", sector: "Finance" },
  { ticker: "USB", name: "U.S. Bancorp", market: "US", sector: "Finance" },
  { ticker: "AXP", name: "American Express", market: "US", sector: "Finance" },
  { ticker: "V", name: "Visa", market: "US", sector: "Finance" },
  { ticker: "MA", name: "Mastercard", market: "US", sector: "Finance" },
  { ticker: "MET", name: "MetLife", market: "US", sector: "Finance" },
  { ticker: "BRK-B", name: "Berkshire Hathaway (B)", market: "US", sector: "Finance" },
  { ticker: "SCHW", name: "Charles Schwab", market: "US", sector: "Finance" },
  // Healthcare
  { ticker: "JNJ", name: "Johnson & Johnson", market: "US", sector: "Healthcare" },
  { ticker: "UNH", name: "UnitedHealth", market: "US", sector: "Healthcare" },
  { ticker: "PFE", name: "Pfizer", market: "US", sector: "Healthcare" },
  { ticker: "MRK", name: "Merck", market: "US", sector: "Healthcare" },
  { ticker: "ABBV", name: "AbbVie", market: "US", sector: "Healthcare" },
  { ticker: "LLY", name: "Eli Lilly", market: "US", sector: "Healthcare" },
  { ticker: "AMGN", name: "Amgen", market: "US", sector: "Healthcare" },
  { ticker: "GILD", name: "Gilead Sciences", market: "US", sector: "Healthcare" },
  { ticker: "BMY", name: "Bristol-Myers Squibb", market: "US", sector: "Healthcare" },
  { ticker: "BIIB", name: "Biogen", market: "US", sector: "Healthcare" },
  { ticker: "CVS", name: "CVS Health", market: "US", sector: "Healthcare" },
  { ticker: "MDT", name: "Medtronic", market: "US", sector: "Healthcare" },
  { ticker: "TMO", name: "Thermo Fisher", market: "US", sector: "Healthcare" },
  { ticker: "ISRG", name: "Intuitive Surgical", market: "US", sector: "Healthcare" },
  { ticker: "DHR", name: "Danaher", market: "US", sector: "Healthcare" },
  // Consumer
  { ticker: "KO", name: "Coca-Cola", market: "US", sector: "Consumer" },
  { ticker: "PEP", name: "PepsiCo", market: "US", sector: "Consumer" },
  { ticker: "PG", name: "Procter & Gamble", market: "US", sector: "Consumer" },
  { ticker: "WMT", name: "Walmart", market: "US", sector: "Consumer" },
  { ticker: "COST", name: "Costco", market: "US", sector: "Consumer" },
  { ticker: "HD", name: "Home Depot", market: "US", sector: "Consumer" },
  { ticker: "LOW", name: "Lowe's", market: "US", sector: "Consumer" },
  { ticker: "MCD", name: "McDonald's", market: "US", sector: "Consumer" },
  { ticker: "SBUX", name: "Starbucks", market: "US", sector: "Consumer" },
  { ticker: "NKE", name: "Nike", market: "US", sector: "Consumer" },
  { ticker: "TGT", name: "Target", market: "US", sector: "Consumer" },
  { ticker: "CL", name: "Colgate-Palmolive", market: "US", sector: "Consumer" },
  { ticker: "DIS", name: "Walt Disney", market: "US", sector: "Consumer" },
  { ticker: "CMCSA", name: "Comcast", market: "US", sector: "Consumer" },
  { ticker: "MO", name: "Altria Group", market: "US", sector: "Consumer" },
  { ticker: "PM", name: "Philip Morris Intl", market: "US", sector: "Consumer" },
  // Industrial
  { ticker: "CAT", name: "Caterpillar", market: "US", sector: "Industrial" },
  { ticker: "BA", name: "Boeing", market: "US", sector: "Industrial" },
  { ticker: "HON", name: "Honeywell", market: "US", sector: "Industrial" },
  { ticker: "GE", name: "GE Aerospace", market: "US", sector: "Industrial" },
  { ticker: "DE", name: "Deere & Co", market: "US", sector: "Industrial" },
  { ticker: "LMT", name: "Lockheed Martin", market: "US", sector: "Industrial" },
  { ticker: "RTX", name: "RTX Corp", market: "US", sector: "Industrial" },
  { ticker: "GD", name: "General Dynamics", market: "US", sector: "Industrial" },
  { ticker: "EMR", name: "Emerson Electric", market: "US", sector: "Industrial" },
  { ticker: "UNP", name: "Union Pacific", market: "US", sector: "Industrial" },
  { ticker: "UPS", name: "UPS", market: "US", sector: "Industrial" },
  { ticker: "MMM", name: "3M", market: "US", sector: "Industrial" },
  { ticker: "F", name: "Ford Motor", market: "US", sector: "Industrial" },
  { ticker: "GM", name: "General Motors", market: "US", sector: "Industrial" },
  // Energy
  { ticker: "XOM", name: "Exxon Mobil", market: "US", sector: "Energy" },
  { ticker: "CVX", name: "Chevron", market: "US", sector: "Energy" },
  { ticker: "COP", name: "ConocoPhillips", market: "US", sector: "Energy" },
  { ticker: "EOG", name: "EOG Resources", market: "US", sector: "Energy" },
  { ticker: "SLB", name: "Schlumberger", market: "US", sector: "Energy" },
  // Utilities / Telecom
  { ticker: "NEE", name: "NextEra Energy", market: "US", sector: "Utilities" },
  { ticker: "DUK", name: "Duke Energy", market: "US", sector: "Utilities" },
  { ticker: "SO", name: "Southern Co", market: "US", sector: "Utilities" },
  { ticker: "EXC", name: "Exelon", market: "US", sector: "Utilities" },
  { ticker: "LIN", name: "Linde", market: "US", sector: "Utilities" },
  { ticker: "T", name: "AT&T", market: "US", sector: "Telecom" },
  { ticker: "VZ", name: "Verizon", market: "US", sector: "Telecom" },
];

// ── 台股 (0050 + 0051 成分 + 熱門中小型) ────────────────────────

const TW_STOCKS: StockEntry[] = [
  // 半導體
  { ticker: "2330.TW", name: "台積電", market: "TW", sector: "半導體" },
  { ticker: "2303.TW", name: "聯電", market: "TW", sector: "半導體" },
  { ticker: "2454.TW", name: "聯發科", market: "TW", sector: "半導體" },
  { ticker: "3711.TW", name: "日月光投控", market: "TW", sector: "半導體" },
  { ticker: "2379.TW", name: "瑞昱", market: "TW", sector: "半導體" },
  { ticker: "3034.TW", name: "聯詠", market: "TW", sector: "半導體" },
  { ticker: "2408.TW", name: "南亞科", market: "TW", sector: "半導體" },
  { ticker: "3529.TW", name: "力旺", market: "TW", sector: "半導體" },
  { ticker: "6415.TW", name: "矽力-KY", market: "TW", sector: "半導體" },
  { ticker: "3443.TW", name: "創意", market: "TW", sector: "半導體" },
  { ticker: "6488.TW", name: "環球晶", market: "TW", sector: "半導體" },
  { ticker: "5274.TW", name: "信驊", market: "TW", sector: "半導體" },
  { ticker: "3661.TW", name: "世芯-KY", market: "TW", sector: "半導體" },
  { ticker: "2449.TW", name: "京元電子", market: "TW", sector: "半導體" },
  // 電子 / 資通訊
  { ticker: "2317.TW", name: "鴻海", market: "TW", sector: "電子" },
  { ticker: "2382.TW", name: "廣達", market: "TW", sector: "電子" },
  { ticker: "2308.TW", name: "台達電", market: "TW", sector: "電子" },
  { ticker: "2357.TW", name: "華碩", market: "TW", sector: "電子" },
  { ticker: "3231.TW", name: "緯創", market: "TW", sector: "電子" },
  { ticker: "2345.TW", name: "智邦", market: "TW", sector: "電子" },
  { ticker: "2395.TW", name: "研華", market: "TW", sector: "電子" },
  { ticker: "2301.TW", name: "光寶科", market: "TW", sector: "電子" },
  { ticker: "3037.TW", name: "欣興", market: "TW", sector: "電子" },
  { ticker: "2356.TW", name: "英業達", market: "TW", sector: "電子" },
  { ticker: "2353.TW", name: "宏碁", market: "TW", sector: "電子" },
  { ticker: "2354.TW", name: "鴻準", market: "TW", sector: "電子" },
  { ticker: "2383.TW", name: "台光電", market: "TW", sector: "電子" },
  { ticker: "3017.TW", name: "奇鋐", market: "TW", sector: "電子" },
  { ticker: "3044.TW", name: "健鼎", market: "TW", sector: "電子" },
  { ticker: "6669.TW", name: "緯穎", market: "TW", sector: "電子" },
  { ticker: "2327.TW", name: "國巨", market: "TW", sector: "電子" },
  { ticker: "3036.TW", name: "文曄", market: "TW", sector: "電子" },
  { ticker: "3533.TW", name: "嘉澤", market: "TW", sector: "電子" },
  { ticker: "2474.TW", name: "可成", market: "TW", sector: "電子" },
  { ticker: "2049.TW", name: "上銀", market: "TW", sector: "電子" },
  // 金融
  { ticker: "2881.TW", name: "富邦金", market: "TW", sector: "金融" },
  { ticker: "2882.TW", name: "國泰金", market: "TW", sector: "金融" },
  { ticker: "2884.TW", name: "玉山金", market: "TW", sector: "金融" },
  { ticker: "2886.TW", name: "兆豐金", market: "TW", sector: "金融" },
  { ticker: "2891.TW", name: "中信金", market: "TW", sector: "金融" },
  { ticker: "2880.TW", name: "華南金", market: "TW", sector: "金融" },
  { ticker: "2883.TW", name: "開發金", market: "TW", sector: "金融" },
  { ticker: "2887.TW", name: "台新金", market: "TW", sector: "金融" },
  { ticker: "2890.TW", name: "永豐金", market: "TW", sector: "金融" },
  { ticker: "2892.TW", name: "第一金", market: "TW", sector: "金融" },
  { ticker: "5880.TW", name: "合庫金", market: "TW", sector: "金融" },
  { ticker: "2885.TW", name: "元大金", market: "TW", sector: "金融" },
  { ticker: "2888.TW", name: "新光金", market: "TW", sector: "金融" },
  { ticker: "2889.TW", name: "國票金", market: "TW", sector: "金融" },
  { ticker: "5876.TW", name: "上海商銀", market: "TW", sector: "金融" },
  { ticker: "2867.TW", name: "三商壽", market: "TW", sector: "金融" },
  // 傳產 / 塑化
  { ticker: "1301.TW", name: "台塑", market: "TW", sector: "塑化" },
  { ticker: "1303.TW", name: "南亞", market: "TW", sector: "塑化" },
  { ticker: "1326.TW", name: "台化", market: "TW", sector: "塑化" },
  { ticker: "6505.TW", name: "台塑化", market: "TW", sector: "塑化" },
  { ticker: "1402.TW", name: "遠東新", market: "TW", sector: "塑化" },
  // 鋼鐵 / 水泥
  { ticker: "2002.TW", name: "中鋼", market: "TW", sector: "鋼鐵水泥" },
  { ticker: "1101.TW", name: "台泥", market: "TW", sector: "鋼鐵水泥" },
  { ticker: "1102.TW", name: "亞泥", market: "TW", sector: "鋼鐵水泥" },
  // 食品 / 零售
  { ticker: "1216.TW", name: "統一", market: "TW", sector: "食品零售" },
  { ticker: "2912.TW", name: "統一超", market: "TW", sector: "食品零售" },
  { ticker: "1210.TW", name: "大成", market: "TW", sector: "食品零售" },
  { ticker: "1227.TW", name: "佳格", market: "TW", sector: "食品零售" },
  { ticker: "2915.TW", name: "潤泰全", market: "TW", sector: "食品零售" },
  // 紡織 / 製鞋
  { ticker: "9910.TW", name: "豐泰", market: "TW", sector: "紡織製鞋" },
  { ticker: "9904.TW", name: "寶成", market: "TW", sector: "紡織製鞋" },
  { ticker: "1477.TW", name: "聚陽", market: "TW", sector: "紡織製鞋" },
  // 汽車
  { ticker: "2207.TW", name: "和泰車", market: "TW", sector: "汽車" },
  { ticker: "2201.TW", name: "裕隆", market: "TW", sector: "汽車" },
  // 電信
  { ticker: "2412.TW", name: "中華電", market: "TW", sector: "電信" },
  { ticker: "3045.TW", name: "台灣大", market: "TW", sector: "電信" },
  { ticker: "4904.TW", name: "遠傳", market: "TW", sector: "電信" },
  // 航運
  { ticker: "2603.TW", name: "長榮", market: "TW", sector: "航運" },
  { ticker: "2609.TW", name: "陽明", market: "TW", sector: "航運" },
  { ticker: "2615.TW", name: "萬海", market: "TW", sector: "航運" },
  { ticker: "2618.TW", name: "長榮航", market: "TW", sector: "航運" },
  // 營建 / 資產
  { ticker: "2504.TW", name: "國產", market: "TW", sector: "營建" },
  { ticker: "2542.TW", name: "興富發", market: "TW", sector: "營建" },
  { ticker: "2545.TW", name: "皇翔", market: "TW", sector: "營建" },
  // 生技醫療
  { ticker: "4743.TW", name: "合一", market: "TW", sector: "生技" },
  { ticker: "6446.TW", name: "藥華藥", market: "TW", sector: "生技" },
  { ticker: "1760.TW", name: "寶齡富錦", market: "TW", sector: "生技" },
  { ticker: "4968.TW", name: "立積", market: "TW", sector: "生技" },
  // 觀光
  { ticker: "2712.TW", name: "遠雄來", market: "TW", sector: "觀光" },
  { ticker: "2706.TW", name: "第一店", market: "TW", sector: "觀光" },
];

// ── ETF (資產配置 / 板塊輪動用) ──────────────────────────────

const ETF_STOCKS: StockEntry[] = [
  // 美股大盤 ETF
  { ticker: "SPY", name: "S&P 500 ETF", market: "ETF", sector: "美股大盤" },
  { ticker: "QQQ", name: "Nasdaq 100 ETF", market: "ETF", sector: "美股大盤" },
  { ticker: "IWM", name: "Russell 2000 小型股", market: "ETF", sector: "美股大盤" },
  { ticker: "DIA", name: "Dow Jones ETF", market: "ETF", sector: "美股大盤" },
  { ticker: "VOO", name: "Vanguard S&P 500", market: "ETF", sector: "美股大盤" },
  { ticker: "VTI", name: "Vanguard 全美股", market: "ETF", sector: "美股大盤" },
  // 美股板塊 ETF
  { ticker: "XLK", name: "科技板塊 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLF", name: "金融板塊 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLV", name: "醫療板塊 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLE", name: "能源板塊 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLY", name: "非必需消費 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLP", name: "必需消費 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLI", name: "工業板塊 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLU", name: "公用事業 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLB", name: "原材料 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "XLRE", name: "不動產 ETF", market: "ETF", sector: "美股板塊" },
  { ticker: "SMH", name: "半導體 ETF", market: "ETF", sector: "美股板塊" },
  // 國際 / 新興市場
  { ticker: "EFA", name: "EAFE 已開發市場", market: "ETF", sector: "國際市場" },
  { ticker: "EEM", name: "新興市場 ETF", market: "ETF", sector: "國際市場" },
  { ticker: "VWO", name: "Vanguard 新興市場", market: "ETF", sector: "國際市場" },
  { ticker: "FXI", name: "中國大型股 ETF", market: "ETF", sector: "國際市場" },
  { ticker: "EWJ", name: "日本 ETF", market: "ETF", sector: "國際市場" },
  { ticker: "EWT", name: "台灣 ETF (MSCI)", market: "ETF", sector: "國際市場" },
  // 債券
  { ticker: "TLT", name: "20年+美國公債", market: "ETF", sector: "債券" },
  { ticker: "IEF", name: "7-10年美國公債", market: "ETF", sector: "債券" },
  { ticker: "SHY", name: "1-3年美國公債", market: "ETF", sector: "債券" },
  { ticker: "LQD", name: "投資級公司債", market: "ETF", sector: "債券" },
  { ticker: "HYG", name: "高收益公司債", market: "ETF", sector: "債券" },
  { ticker: "AGG", name: "綜合債券 ETF", market: "ETF", sector: "債券" },
  // 商品
  { ticker: "GLD", name: "黃金 ETF", market: "ETF", sector: "商品" },
  { ticker: "SLV", name: "白銀 ETF", market: "ETF", sector: "商品" },
  { ticker: "USO", name: "原油 ETF", market: "ETF", sector: "商品" },
  { ticker: "DBA", name: "農產品 ETF", market: "ETF", sector: "商品" },
  // 台股 ETF
  { ticker: "0050.TW", name: "元大台灣50", market: "ETF", sector: "台股ETF" },
  { ticker: "0051.TW", name: "元大中型100", market: "ETF", sector: "台股ETF" },
  { ticker: "0052.TW", name: "富邦科技", market: "ETF", sector: "台股ETF" },
  { ticker: "0055.TW", name: "元大MSCI金融", market: "ETF", sector: "台股ETF" },
  { ticker: "0056.TW", name: "元大高股息", market: "ETF", sector: "台股ETF" },
  { ticker: "006205.TW", name: "富邦上証", market: "ETF", sector: "台股ETF" },
  { ticker: "006208.TW", name: "富邦台50", market: "ETF", sector: "台股ETF" },
  { ticker: "00878.TW", name: "國泰永續高股息", market: "ETF", sector: "台股ETF" },
  { ticker: "00881.TW", name: "國泰台灣5G+", market: "ETF", sector: "台股ETF" },
  { ticker: "00713.TW", name: "元大台灣高息低波", market: "ETF", sector: "台股ETF" },
  { ticker: "00919.TW", name: "群益台灣精選高息", market: "ETF", sector: "台股ETF" },
  { ticker: "00929.TW", name: "復華台灣科技優息", market: "ETF", sector: "台股ETF" },
  { ticker: "00940.TW", name: "元大台灣價值高息", market: "ETF", sector: "台股ETF" },
];

export const STOCK_LIST: StockEntry[] = [...US_STOCKS, ...TW_STOCKS, ...ETF_STOCKS];

// ── 預設組合 ────────────────────────────────────────────────

export type PresetKey = string;

export interface Preset {
  key: PresetKey;
  label: string;
  labelZh: string;
  tickers: string[];
}

const byMarketSector = (market: "US" | "TW" | "ETF", sector?: string) =>
  STOCK_LIST.filter((s) => s.market === market && (!sector || s.sector === sector)).map((s) => s.ticker);

export const PRESETS: Preset[] = [
  // US
  { key: "us_all", label: "US All", labelZh: "美股全部", tickers: byMarketSector("US") },
  { key: "us_tech", label: "US Tech", labelZh: "美股科技", tickers: byMarketSector("US", "Technology") },
  { key: "us_finance", label: "US Finance", labelZh: "美股金融", tickers: byMarketSector("US", "Finance") },
  { key: "us_health", label: "US Healthcare", labelZh: "美股醫療", tickers: byMarketSector("US", "Healthcare") },
  { key: "us_consumer", label: "US Consumer", labelZh: "美股消費", tickers: byMarketSector("US", "Consumer") },
  { key: "us_industrial", label: "US Industrial", labelZh: "美股工業", tickers: byMarketSector("US", "Industrial") },
  // TW
  { key: "tw_all", label: "TW All", labelZh: "台股全部", tickers: byMarketSector("TW") },
  { key: "tw_semi", label: "TW Semiconductor", labelZh: "台股半導體", tickers: byMarketSector("TW", "半導體") },
  { key: "tw_elec", label: "TW Electronic", labelZh: "台股電子", tickers: byMarketSector("TW", "電子") },
  { key: "tw_fin", label: "TW Finance", labelZh: "台股金融", tickers: byMarketSector("TW", "金融") },
  { key: "tw_trad", label: "TW Traditional", labelZh: "台股傳產", tickers: [...byMarketSector("TW", "塑化"), ...byMarketSector("TW", "鋼鐵水泥"), ...byMarketSector("TW", "食品零售"), ...byMarketSector("TW", "紡織製鞋")] },
  { key: "tw_ship", label: "TW Shipping", labelZh: "台股航運", tickers: byMarketSector("TW", "航運") },
  // ETF
  { key: "etf_all", label: "ETF All", labelZh: "ETF 全部", tickers: byMarketSector("ETF") },
  { key: "etf_sector", label: "US Sector Rotation", labelZh: "美股板塊輪動", tickers: byMarketSector("ETF", "美股板塊") },
  { key: "etf_global", label: "Global Allocation", labelZh: "全球資產配置", tickers: ["SPY", "EFA", "EEM", "TLT", "GLD", "USO"] },
  { key: "etf_tw", label: "TW ETF", labelZh: "台股 ETF", tickers: byMarketSector("ETF", "台股ETF") },
  { key: "etf_bond", label: "Bond ETF", labelZh: "債券 ETF", tickers: byMarketSector("ETF", "債券") },
];
