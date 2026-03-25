package com.quant.trading.data

/**
 * Stock universe data for the UniversePicker.
 * Mirrors the web frontend's stocks.ts data.
 */

data class StockEntry(
    val ticker: String,
    val name: String,
    val market: Market,
    val sector: String? = null,
)

enum class Market { US, TW, ETF }

data class Preset(
    val key: String,
    val label: String,
    val labelZh: String,
    val tickers: List<String>,
)

// ── US Stocks (S&P 500 select ~110) ──────────────────────────────────

private val US_STOCKS = listOf(
    // Technology
    StockEntry("AAPL", "Apple", Market.US, "Technology"),
    StockEntry("MSFT", "Microsoft", Market.US, "Technology"),
    StockEntry("GOOGL", "Alphabet (A)", Market.US, "Technology"),
    StockEntry("GOOG", "Alphabet (C)", Market.US, "Technology"),
    StockEntry("META", "Meta Platforms", Market.US, "Technology"),
    StockEntry("NVDA", "NVIDIA", Market.US, "Technology"),
    StockEntry("AMZN", "Amazon", Market.US, "Technology"),
    StockEntry("TSLA", "Tesla", Market.US, "Technology"),
    StockEntry("CRM", "Salesforce", Market.US, "Technology"),
    StockEntry("CSCO", "Cisco Systems", Market.US, "Technology"),
    StockEntry("INTC", "Intel", Market.US, "Technology"),
    StockEntry("IBM", "IBM", Market.US, "Technology"),
    StockEntry("ORCL", "Oracle", Market.US, "Technology"),
    StockEntry("QCOM", "Qualcomm", Market.US, "Technology"),
    StockEntry("TXN", "Texas Instruments", Market.US, "Technology"),
    StockEntry("PYPL", "PayPal", Market.US, "Technology"),
    StockEntry("ADBE", "Adobe", Market.US, "Technology"),
    StockEntry("AVGO", "Broadcom", Market.US, "Technology"),
    StockEntry("AMD", "AMD", Market.US, "Technology"),
    StockEntry("NFLX", "Netflix", Market.US, "Technology"),
    StockEntry("UBER", "Uber", Market.US, "Technology"),
    StockEntry("NOW", "ServiceNow", Market.US, "Technology"),
    StockEntry("SHOP", "Shopify", Market.US, "Technology"),
    StockEntry("SQ", "Block (Square)", Market.US, "Technology"),
    StockEntry("SNOW", "Snowflake", Market.US, "Technology"),
    StockEntry("PLTR", "Palantir", Market.US, "Technology"),
    StockEntry("MU", "Micron Technology", Market.US, "Technology"),
    StockEntry("AMAT", "Applied Materials", Market.US, "Technology"),
    StockEntry("LRCX", "Lam Research", Market.US, "Technology"),
    StockEntry("KLAC", "KLA Corp", Market.US, "Technology"),
    // Finance
    StockEntry("JPM", "JPMorgan Chase", Market.US, "Finance"),
    StockEntry("BAC", "Bank of America", Market.US, "Finance"),
    StockEntry("WFC", "Wells Fargo", Market.US, "Finance"),
    StockEntry("GS", "Goldman Sachs", Market.US, "Finance"),
    StockEntry("MS", "Morgan Stanley", Market.US, "Finance"),
    StockEntry("C", "Citigroup", Market.US, "Finance"),
    StockEntry("BLK", "BlackRock", Market.US, "Finance"),
    StockEntry("BK", "BNY Mellon", Market.US, "Finance"),
    StockEntry("USB", "U.S. Bancorp", Market.US, "Finance"),
    StockEntry("AXP", "American Express", Market.US, "Finance"),
    StockEntry("V", "Visa", Market.US, "Finance"),
    StockEntry("MA", "Mastercard", Market.US, "Finance"),
    StockEntry("MET", "MetLife", Market.US, "Finance"),
    StockEntry("BRK-B", "Berkshire Hathaway (B)", Market.US, "Finance"),
    StockEntry("SCHW", "Charles Schwab", Market.US, "Finance"),
    // Healthcare
    StockEntry("JNJ", "Johnson & Johnson", Market.US, "Healthcare"),
    StockEntry("UNH", "UnitedHealth", Market.US, "Healthcare"),
    StockEntry("PFE", "Pfizer", Market.US, "Healthcare"),
    StockEntry("MRK", "Merck", Market.US, "Healthcare"),
    StockEntry("ABBV", "AbbVie", Market.US, "Healthcare"),
    StockEntry("LLY", "Eli Lilly", Market.US, "Healthcare"),
    StockEntry("AMGN", "Amgen", Market.US, "Healthcare"),
    StockEntry("GILD", "Gilead Sciences", Market.US, "Healthcare"),
    StockEntry("BMY", "Bristol-Myers Squibb", Market.US, "Healthcare"),
    StockEntry("BIIB", "Biogen", Market.US, "Healthcare"),
    StockEntry("CVS", "CVS Health", Market.US, "Healthcare"),
    StockEntry("MDT", "Medtronic", Market.US, "Healthcare"),
    StockEntry("TMO", "Thermo Fisher", Market.US, "Healthcare"),
    StockEntry("ISRG", "Intuitive Surgical", Market.US, "Healthcare"),
    StockEntry("DHR", "Danaher", Market.US, "Healthcare"),
    // Consumer
    StockEntry("KO", "Coca-Cola", Market.US, "Consumer"),
    StockEntry("PEP", "PepsiCo", Market.US, "Consumer"),
    StockEntry("PG", "Procter & Gamble", Market.US, "Consumer"),
    StockEntry("WMT", "Walmart", Market.US, "Consumer"),
    StockEntry("COST", "Costco", Market.US, "Consumer"),
    StockEntry("HD", "Home Depot", Market.US, "Consumer"),
    StockEntry("LOW", "Lowe's", Market.US, "Consumer"),
    StockEntry("MCD", "McDonald's", Market.US, "Consumer"),
    StockEntry("SBUX", "Starbucks", Market.US, "Consumer"),
    StockEntry("NKE", "Nike", Market.US, "Consumer"),
    StockEntry("TGT", "Target", Market.US, "Consumer"),
    StockEntry("CL", "Colgate-Palmolive", Market.US, "Consumer"),
    StockEntry("DIS", "Walt Disney", Market.US, "Consumer"),
    StockEntry("CMCSA", "Comcast", Market.US, "Consumer"),
    StockEntry("MO", "Altria Group", Market.US, "Consumer"),
    StockEntry("PM", "Philip Morris Intl", Market.US, "Consumer"),
    // Industrial
    StockEntry("CAT", "Caterpillar", Market.US, "Industrial"),
    StockEntry("BA", "Boeing", Market.US, "Industrial"),
    StockEntry("HON", "Honeywell", Market.US, "Industrial"),
    StockEntry("GE", "GE Aerospace", Market.US, "Industrial"),
    StockEntry("DE", "Deere & Co", Market.US, "Industrial"),
    StockEntry("LMT", "Lockheed Martin", Market.US, "Industrial"),
    StockEntry("RTX", "RTX Corp", Market.US, "Industrial"),
    StockEntry("GD", "General Dynamics", Market.US, "Industrial"),
    StockEntry("EMR", "Emerson Electric", Market.US, "Industrial"),
    StockEntry("UNP", "Union Pacific", Market.US, "Industrial"),
    StockEntry("UPS", "UPS", Market.US, "Industrial"),
    StockEntry("MMM", "3M", Market.US, "Industrial"),
    StockEntry("F", "Ford Motor", Market.US, "Industrial"),
    StockEntry("GM", "General Motors", Market.US, "Industrial"),
    // Energy
    StockEntry("XOM", "Exxon Mobil", Market.US, "Energy"),
    StockEntry("CVX", "Chevron", Market.US, "Energy"),
    StockEntry("COP", "ConocoPhillips", Market.US, "Energy"),
    StockEntry("EOG", "EOG Resources", Market.US, "Energy"),
    StockEntry("SLB", "Schlumberger", Market.US, "Energy"),
    // Utilities / Telecom
    StockEntry("NEE", "NextEra Energy", Market.US, "Utilities"),
    StockEntry("DUK", "Duke Energy", Market.US, "Utilities"),
    StockEntry("SO", "Southern Co", Market.US, "Utilities"),
    StockEntry("EXC", "Exelon", Market.US, "Utilities"),
    StockEntry("LIN", "Linde", Market.US, "Utilities"),
    StockEntry("T", "AT&T", Market.US, "Telecom"),
    StockEntry("VZ", "Verizon", Market.US, "Telecom"),
)

// ── TW Stocks ────────────────────────────────────────────────────────

private val TW_STOCKS = listOf(
    // 半導體
    StockEntry("2330.TW", "台積電", Market.TW, "半導體"),
    StockEntry("2303.TW", "聯電", Market.TW, "半導體"),
    StockEntry("2454.TW", "聯發科", Market.TW, "半導體"),
    StockEntry("3711.TW", "日月光投控", Market.TW, "半導體"),
    StockEntry("2379.TW", "瑞昱", Market.TW, "半導體"),
    StockEntry("3034.TW", "聯詠", Market.TW, "半導體"),
    StockEntry("2408.TW", "南亞科", Market.TW, "半導體"),
    StockEntry("3529.TW", "力旺", Market.TW, "半導體"),
    StockEntry("6415.TW", "矽力-KY", Market.TW, "半導體"),
    StockEntry("3443.TW", "創意", Market.TW, "半導體"),
    StockEntry("6488.TW", "環球晶", Market.TW, "半導體"),
    StockEntry("5274.TW", "信驊", Market.TW, "半導體"),
    StockEntry("3661.TW", "世芯-KY", Market.TW, "半導體"),
    StockEntry("2449.TW", "京元電子", Market.TW, "半導體"),
    // 電子 / 資通訊
    StockEntry("2317.TW", "鴻海", Market.TW, "電子"),
    StockEntry("2382.TW", "廣達", Market.TW, "電子"),
    StockEntry("2308.TW", "台達電", Market.TW, "電子"),
    StockEntry("2357.TW", "華碩", Market.TW, "電子"),
    StockEntry("3231.TW", "緯創", Market.TW, "電子"),
    StockEntry("2345.TW", "智邦", Market.TW, "電子"),
    StockEntry("2395.TW", "研華", Market.TW, "電子"),
    StockEntry("2301.TW", "光寶科", Market.TW, "電子"),
    StockEntry("3037.TW", "欣興", Market.TW, "電子"),
    StockEntry("2356.TW", "英業達", Market.TW, "電子"),
    StockEntry("2353.TW", "宏碁", Market.TW, "電子"),
    StockEntry("2354.TW", "鴻準", Market.TW, "電子"),
    StockEntry("2383.TW", "台光電", Market.TW, "電子"),
    StockEntry("3017.TW", "奇鋐", Market.TW, "電子"),
    StockEntry("3044.TW", "健鼎", Market.TW, "電子"),
    StockEntry("6669.TW", "緯穎", Market.TW, "電子"),
    StockEntry("2327.TW", "國巨", Market.TW, "電子"),
    StockEntry("3036.TW", "文曄", Market.TW, "電子"),
    StockEntry("3533.TW", "嘉澤", Market.TW, "電子"),
    StockEntry("2474.TW", "可成", Market.TW, "電子"),
    StockEntry("2049.TW", "上銀", Market.TW, "電子"),
    // 金融
    StockEntry("2881.TW", "富邦金", Market.TW, "金融"),
    StockEntry("2882.TW", "國泰金", Market.TW, "金融"),
    StockEntry("2884.TW", "玉山金", Market.TW, "金融"),
    StockEntry("2886.TW", "兆豐金", Market.TW, "金融"),
    StockEntry("2891.TW", "中信金", Market.TW, "金融"),
    StockEntry("2880.TW", "華南金", Market.TW, "金融"),
    StockEntry("2883.TW", "開發金", Market.TW, "金融"),
    StockEntry("2887.TW", "台新金", Market.TW, "金融"),
    StockEntry("2890.TW", "永豐金", Market.TW, "金融"),
    StockEntry("2892.TW", "第一金", Market.TW, "金融"),
    StockEntry("5880.TW", "合庫金", Market.TW, "金融"),
    StockEntry("2885.TW", "元大金", Market.TW, "金融"),
    StockEntry("2888.TW", "新光金", Market.TW, "金融"),
    StockEntry("2889.TW", "國票金", Market.TW, "金融"),
    StockEntry("5876.TW", "上海商銀", Market.TW, "金融"),
    StockEntry("2867.TW", "三商壽", Market.TW, "金融"),
    // 塑化
    StockEntry("1301.TW", "台塑", Market.TW, "塑化"),
    StockEntry("1303.TW", "南亞", Market.TW, "塑化"),
    StockEntry("1326.TW", "台化", Market.TW, "塑化"),
    StockEntry("6505.TW", "台塑化", Market.TW, "塑化"),
    StockEntry("1402.TW", "遠東新", Market.TW, "塑化"),
    // 鋼鐵水泥
    StockEntry("2002.TW", "中鋼", Market.TW, "鋼鐵水泥"),
    StockEntry("1101.TW", "台泥", Market.TW, "鋼鐵水泥"),
    StockEntry("1102.TW", "亞泥", Market.TW, "鋼鐵水泥"),
    // 食品零售
    StockEntry("1216.TW", "統一", Market.TW, "食品零售"),
    StockEntry("2912.TW", "統一超", Market.TW, "食品零售"),
    StockEntry("1210.TW", "大成", Market.TW, "食品零售"),
    StockEntry("1227.TW", "佳格", Market.TW, "食品零售"),
    StockEntry("2915.TW", "潤泰全", Market.TW, "食品零售"),
    // 紡織製鞋
    StockEntry("9910.TW", "豐泰", Market.TW, "紡織製鞋"),
    StockEntry("9904.TW", "寶成", Market.TW, "紡織製鞋"),
    StockEntry("1477.TW", "聚陽", Market.TW, "紡織製鞋"),
    // 汽車
    StockEntry("2207.TW", "和泰車", Market.TW, "汽車"),
    StockEntry("2201.TW", "裕隆", Market.TW, "汽車"),
    // 電信
    StockEntry("2412.TW", "中華電", Market.TW, "電信"),
    StockEntry("3045.TW", "台灣大", Market.TW, "電信"),
    StockEntry("4904.TW", "遠傳", Market.TW, "電信"),
    // 航運
    StockEntry("2603.TW", "長榮", Market.TW, "航運"),
    StockEntry("2609.TW", "陽明", Market.TW, "航運"),
    StockEntry("2615.TW", "萬海", Market.TW, "航運"),
    StockEntry("2618.TW", "長榮航", Market.TW, "航運"),
    // 營建
    StockEntry("2504.TW", "國產", Market.TW, "營建"),
    StockEntry("2542.TW", "興富發", Market.TW, "營建"),
    StockEntry("2545.TW", "皇翔", Market.TW, "營建"),
    // 生技
    StockEntry("4743.TW", "合一", Market.TW, "生技"),
    StockEntry("6446.TW", "藥華藥", Market.TW, "生技"),
    StockEntry("1760.TW", "寶齡富錦", Market.TW, "生技"),
    StockEntry("4968.TW", "立積", Market.TW, "生技"),
    // 觀光
    StockEntry("2712.TW", "遠雄來", Market.TW, "觀光"),
    StockEntry("2706.TW", "第一店", Market.TW, "觀光"),
)

// ── ETFs ──────────────────────────────────────────────────────────────

private val ETF_STOCKS = listOf(
    // 美股大盤
    StockEntry("SPY", "S&P 500 ETF", Market.ETF, "美股大盤"),
    StockEntry("QQQ", "Nasdaq 100 ETF", Market.ETF, "美股大盤"),
    StockEntry("IWM", "Russell 2000 小型股", Market.ETF, "美股大盤"),
    StockEntry("DIA", "Dow Jones ETF", Market.ETF, "美股大盤"),
    StockEntry("VOO", "Vanguard S&P 500", Market.ETF, "美股大盤"),
    StockEntry("VTI", "Vanguard 全美股", Market.ETF, "美股大盤"),
    // 美股板塊
    StockEntry("XLK", "科技板塊 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLF", "金融板塊 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLV", "醫療板塊 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLE", "能源板塊 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLY", "非必需消費 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLP", "必需消費 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLI", "工業板塊 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLU", "公用事業 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLB", "原材料 ETF", Market.ETF, "美股板塊"),
    StockEntry("XLRE", "不動產 ETF", Market.ETF, "美股板塊"),
    StockEntry("SMH", "半導體 ETF", Market.ETF, "美股板塊"),
    // 國際市場
    StockEntry("EFA", "EAFE 已開發市場", Market.ETF, "國際市場"),
    StockEntry("EEM", "新興市場 ETF", Market.ETF, "國際市場"),
    StockEntry("VWO", "Vanguard 新興市場", Market.ETF, "國際市場"),
    StockEntry("FXI", "中國大型股 ETF", Market.ETF, "國際市場"),
    StockEntry("EWJ", "日本 ETF", Market.ETF, "國際市場"),
    StockEntry("EWT", "台灣 ETF (MSCI)", Market.ETF, "國際市場"),
    // 債券
    StockEntry("TLT", "20年+美國公債", Market.ETF, "債券"),
    StockEntry("IEF", "7-10年美國公債", Market.ETF, "債券"),
    StockEntry("SHY", "1-3年美國公債", Market.ETF, "債券"),
    StockEntry("LQD", "投資級公司債", Market.ETF, "債券"),
    StockEntry("HYG", "高收益公司債", Market.ETF, "債券"),
    StockEntry("AGG", "綜合債券 ETF", Market.ETF, "債券"),
    // 商品
    StockEntry("GLD", "黃金 ETF", Market.ETF, "商品"),
    StockEntry("SLV", "白銀 ETF", Market.ETF, "商品"),
    StockEntry("USO", "原油 ETF", Market.ETF, "商品"),
    StockEntry("DBA", "農產品 ETF", Market.ETF, "商品"),
    // 台股ETF
    StockEntry("0050.TW", "元大台灣50", Market.ETF, "台股ETF"),
    StockEntry("0051.TW", "元大中型100", Market.ETF, "台股ETF"),
    StockEntry("0052.TW", "富邦科技", Market.ETF, "台股ETF"),
    StockEntry("0055.TW", "元大MSCI金融", Market.ETF, "台股ETF"),
    StockEntry("0056.TW", "元大高股息", Market.ETF, "台股ETF"),
    StockEntry("006205.TW", "富邦上証", Market.ETF, "台股ETF"),
    StockEntry("006208.TW", "富邦台50", Market.ETF, "台股ETF"),
    StockEntry("00878.TW", "國泰永續高股息", Market.ETF, "台股ETF"),
    StockEntry("00881.TW", "國泰台灣5G+", Market.ETF, "台股ETF"),
    StockEntry("00713.TW", "元大台灣高息低波", Market.ETF, "台股ETF"),
    StockEntry("00919.TW", "群益台灣精選高息", Market.ETF, "台股ETF"),
    StockEntry("00929.TW", "復華台灣科技優息", Market.ETF, "台股ETF"),
    StockEntry("00940.TW", "元大台灣價值高息", Market.ETF, "台股ETF"),
)

// ── Public API ───────────────────────────────────────────────────────

val STOCK_LIST: List<StockEntry> = US_STOCKS + TW_STOCKS + ETF_STOCKS

private fun byMarketSector(market: Market, sector: String? = null): List<String> =
    STOCK_LIST.filter { it.market == market && (sector == null || it.sector == sector) }
        .map { it.ticker }

val PRESETS: List<Preset> = listOf(
    // US
    Preset("us_all", "US All", "美股全部", byMarketSector(Market.US)),
    Preset("us_tech", "US Tech", "美股科技", byMarketSector(Market.US, "Technology")),
    Preset("us_finance", "US Finance", "美股金融", byMarketSector(Market.US, "Finance")),
    Preset("us_health", "US Healthcare", "美股醫療", byMarketSector(Market.US, "Healthcare")),
    Preset("us_consumer", "US Consumer", "美股消費", byMarketSector(Market.US, "Consumer")),
    Preset("us_industrial", "US Industrial", "美股工業", byMarketSector(Market.US, "Industrial")),
    // TW
    Preset("tw_all", "TW All", "台股全部", byMarketSector(Market.TW)),
    Preset("tw_semi", "TW Semiconductor", "台股半導體", byMarketSector(Market.TW, "半導體")),
    Preset("tw_elec", "TW Electronic", "台股電子", byMarketSector(Market.TW, "電子")),
    Preset("tw_fin", "TW Finance", "台股金融", byMarketSector(Market.TW, "金融")),
    Preset(
        "tw_trad", "TW Traditional", "台股傳產",
        byMarketSector(Market.TW, "塑化") +
            byMarketSector(Market.TW, "鋼鐵水泥") +
            byMarketSector(Market.TW, "食品零售") +
            byMarketSector(Market.TW, "紡織製鞋"),
    ),
    Preset("tw_ship", "TW Shipping", "台股航運", byMarketSector(Market.TW, "航運")),
    // ETF
    Preset("etf_all", "ETF All", "ETF 全部", byMarketSector(Market.ETF)),
    Preset("etf_sector", "US Sector Rotation", "美股板塊輪動", byMarketSector(Market.ETF, "美股板塊")),
    Preset("etf_global", "Global Allocation", "全球資產配置", listOf("SPY", "EFA", "EEM", "TLT", "GLD", "USO")),
    Preset("etf_tw", "TW ETF", "台股 ETF", byMarketSector(Market.ETF, "台股ETF")),
    Preset("etf_bond", "Bond ETF", "債券 ETF", byMarketSector(Market.ETF, "債券")),
)
