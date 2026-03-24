import { useT } from "@core/i18n";

export function ChapterFAQ({ section }: { section?: string }) {
  const { lang } = useT();
  const t = (en: string, zh: string) => (lang === "zh" ? zh : en);

  const QA = ({
    q,
    children,
  }: {
    q: string;
    children: React.ReactNode;
  }) => (
    <div className="mb-5">
      <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-2">
        Q: {q}
      </h4>
      <div className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 pl-4 border-l-2 border-slate-200 dark:border-slate-700">
        {children}
      </div>
    </div>
  );

  return (
    <div className="space-y-2">
      {/* ── Section: faq-general ── */}
      {(!section || section === "faq-general") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("General Questions", "一般問題")}
          </h2>

          <QA q={t("Does the system support US stocks?", "系統支援美股嗎？")}>
            <p className="mb-2">
              {t(
                "Yes. The system fully supports US stocks, US ETFs (including bond and commodity ETFs), and Taiwan stocks. Data for US markets is sourced from Yahoo Finance. For Taiwan stocks, you can use either Yahoo Finance or FinMind. The system auto-detects asset type from the ticker symbol — symbols ending in .TW or .TWO are treated as Taiwan stocks, while symbols like AAPL, MSFT, or SPY are treated as US instruments.",
                "是的。系統完全支援美股、美國 ETF（包括債券和商品 ETF）以及台股。美國市場數據來自 Yahoo Finance。台股部分，您可以使用 Yahoo Finance 或 FinMind。系統會從股票代碼自動偵測資產類型 — 以 .TW 或 .TWO 結尾的代碼視為台股，而 AAPL、MSFT 或 SPY 等代碼視為美國標的。"
              )}
            </p>
          </QA>

          <QA q={t("Do I need programming knowledge to use this system?", "使用此系統需要程式設計知識嗎？")}>
            <p className="mb-2">
              {t(
                "For basic usage — running built-in strategies, viewing backtests, monitoring portfolios — no programming is needed. The web dashboard provides a complete GUI for all core features. However, to create custom strategies or modify factor pipelines, you will need basic Python knowledge. The strategy API is designed to be simple: implement a single on_bar() method that returns target weights as a dictionary.",
                "對於基本使用 — 執行內建策略、查看回測、監控投資組合 — 不需要程式設計知識。Web 儀表板為所有核心功能提供完整的圖形介面。但是，要建立自定義策略或修改因子管線，您需要基本的 Python 知識。策略 API 設計得很簡單：實作一個 on_bar() 方法，回傳目標權重的字典。"
              )}
            </p>
          </QA>

          <QA q={t("What is the minimum capital required?", "最低資金需求是多少？")}>
            <p className="mb-2">
              {t(
                "There is no system-imposed minimum. However, practical constraints apply. Taiwan stocks trade in lots of 1,000 shares (set QUANT_TW_LOT_SIZE=1 for odd-lot trading). For a diversified portfolio of 10 Taiwan stocks at an average price of NT$50, you would need roughly NT$500,000. For US stocks, fractional shares are not yet supported, so you need enough capital to buy at least 1 share of each target position. A reasonable starting point for US stocks is $10,000–$50,000.",
                "系統沒有強制最低資金要求。但實際上有限制。台股以 1,000 股為一交易單位（設定 QUANT_TW_LOT_SIZE=1 可進行零股交易）。對於 10 檔平均價格 NT$50 的台股分散投資組合，您大約需要 NT$500,000。美股部分，尚不支援碎股交易，因此您需要足夠的資金購買每個目標持倉至少 1 股。美股的合理起始金額為 $10,000–$50,000。"
              )}
            </p>
          </QA>

          <QA q={t("Can I run multiple strategies at the same time?", "我可以同時運行多個策略嗎？")}>
            <p className="mb-2">
              {t(
                "Yes. You can create multiple saved portfolios, each with its own strategy and universe. Each portfolio runs independently with its own risk rules and rebalancing schedule. The Multi-Asset strategy even supports a two-layer approach: tactical allocation across asset classes, then within-class stock selection. Be mindful of total capital allocation across portfolios to avoid over-leveraging.",
                "可以。您可以建立多個儲存的投資組合，每個都有自己的策略和投資範圍。每個投資組合獨立運行，有自己的風控規則和再平衡排程。多資產策略甚至支援兩層方法：跨資產類別的戰術配置，然後是類別內的選股。請注意跨投資組合的總資金配置，避免過度槓桿。"
              )}
            </p>
          </QA>

          <QA q={t("Is my data secure?", "我的數據安全嗎？")}>
            <p className="mb-2">
              {t(
                "The system runs entirely on your own machine or private server — no data is sent to third-party analytics services. Authentication uses JWT tokens with PBKDF2-SHA256 password hashing. API keys and broker credentials are stored in your local .env file (never committed to version control). The Docker container runs as a non-root user. All API mutations are logged by the audit middleware. For additional security, configure QUANT_ALLOWED_ORIGINS to restrict CORS access.",
                "系統完全在您自己的機器或私人伺服器上運行 — 不會將數據發送到第三方分析服務。認證使用 JWT 令牌配合 PBKDF2-SHA256 密碼雜湊。API 金鑰和券商憑證儲存在您本地的 .env 檔案中（永不提交到版本控制）。Docker 容器以非 root 使用者運行。所有 API 修改操作都由稽核中介軟體記錄。為了額外的安全性，配置 QUANT_ALLOWED_ORIGINS 來限制 CORS 存取。"
              )}
            </p>
          </QA>
        </div>
      )}

      {/* ── Section: faq-data ── */}
      {(!section || section === "faq-data") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("Data Questions", "數據問題")}
          </h2>

          <QA q={t("What data sources does the system use?", "系統使用什麼數據來源？")}>
            <p className="mb-2">
              {t(
                "Two primary data sources are supported: Yahoo Finance (default) and FinMind. Yahoo Finance provides global coverage including US stocks, ETFs, and Taiwan stocks (via .TW/.TWO suffixes). FinMind specializes in Taiwan market data with higher reliability for local instruments. Set QUANT_DATA_SOURCE=yahoo or QUANT_DATA_SOURCE=finmind in your .env file. For macro economic data (used by the allocation layer), the system pulls from FRED (Federal Reserve Economic Data).",
                "支援兩個主要數據來源：Yahoo Finance（預設）和 FinMind。Yahoo Finance 提供全球覆蓋，包括美股、ETF 和台股（透過 .TW/.TWO 後綴）。FinMind 專精於台灣市場數據，對本地標的具有更高的可靠性。在 .env 檔案中設定 QUANT_DATA_SOURCE=yahoo 或 QUANT_DATA_SOURCE=finmind。對於總體經濟數據（配置層使用），系統從 FRED（聯邦儲備經濟數據）取得。"
              )}
            </p>
          </QA>

          <QA q={t("How far back does historical data go?", "歷史數據可以追溯多遠？")}>
            <p className="mb-2">
              {t(
                "Yahoo Finance typically provides 20+ years of daily data for major US stocks and ETFs, and 10+ years for Taiwan stocks. FinMind covers Taiwan stocks from approximately 2004 onwards. The actual availability depends on when the instrument was listed. For newer IPOs, data starts from the listing date. The system caches downloaded data in Parquet format locally, so repeated backtests don't re-download.",
                "Yahoo Finance 通常為主要美股和 ETF 提供 20 年以上的日線數據，台股提供 10 年以上。FinMind 涵蓋約 2004 年以來的台股數據。實際可用性取決於標的上市時間。對於較新的 IPO，數據從上市日期開始。系統將下載的數據以 Parquet 格式快取在本地，因此重複回測不會重新下載。"
              )}
            </p>
          </QA>

          <QA q={t("Is the data adjusted for splits and dividends?", "數據是否已調整股票分割和股利？")}>
            <p className="mb-2">
              {t(
                "Yes. Yahoo Finance provides split-adjusted and dividend-adjusted closing prices by default. The system uses the 'Adj Close' column which accounts for both stock splits and dividend reinvestment. This means backtest results reflect total returns, not just price returns. FinMind data is similarly adjusted. If you notice unusual price jumps in historical data, it is likely an unadjusted data issue — try clearing the cache and re-downloading.",
                "是的。Yahoo Finance 預設提供經股票分割和股利調整的收盤價。系統使用 'Adj Close' 欄位，該欄位同時考慮了股票分割和股利再投資。這意味著回測結果反映的是總報酬，而非僅價格報酬。FinMind 數據同樣已經過調整。如果您在歷史數據中發現異常的價格跳動，可能是未調整數據的問題 — 嘗試清除快取並重新下載。"
              )}
            </p>
          </QA>

          <QA q={t("Why are data downloads slow?", "為什麼數據下載很慢？")}>
            <p className="mb-2">
              {t(
                "Both Yahoo Finance and FinMind impose rate limits on API requests. The system includes built-in retry logic with exponential backoff to handle rate limiting gracefully. First downloads for a large universe (e.g., 50+ stocks) will be slow because each ticker requires a separate API call. Subsequent runs are fast because data is cached locally in Parquet format. You can check the cache directory at the path configured by your data settings. To force a fresh download, delete the cached .parquet files.",
                "Yahoo Finance 和 FinMind 都對 API 請求施加速率限制。系統內建了帶有指數退避的重試邏輯，以優雅地處理速率限制。首次下載大型投資範圍（例如 50 檔以上股票）的數據會較慢，因為每個股票代碼需要單獨的 API 呼叫。後續執行會很快，因為數據以 Parquet 格式在本地快取。您可以在數據設定配置的路徑查看快取目錄。要強制重新下載，請刪除快取的 .parquet 檔案。"
              )}
            </p>
          </QA>

          <QA q={t("Can I use my own custom data source?", "我可以使用自己的自定義數據來源嗎？")}>
            <p className="mb-2">
              {t(
                "Yes. Create a new Python file in src/data/sources/, subclass DataFeed from src/data/feed.py, and implement the required methods: get_bars(), get_latest_price(), and get_universe(). Your get_bars() must return a DataFrame with columns [open, high, low, close, volume] and a timezone-naive DatetimeIndex. Register your new feed in the create_feed() factory in src/data/sources/__init__.py. Then set QUANT_DATA_SOURCE to your custom source name.",
                "可以。在 src/data/sources/ 中建立新的 Python 檔案，從 src/data/feed.py 繼承 DataFeed，並實作所需的方法：get_bars()、get_latest_price() 和 get_universe()。您的 get_bars() 必須回傳包含 [open, high, low, close, volume] 欄位和時區無關 DatetimeIndex 的 DataFrame。在 src/data/sources/__init__.py 的 create_feed() 工廠中註冊您的新數據源。然後將 QUANT_DATA_SOURCE 設定為您的自定義來源名稱。"
              )}
            </p>
          </QA>
        </div>
      )}

      {/* ── Section: faq-troubleshooting ── */}
      {(!section || section === "faq-troubleshooting") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("Troubleshooting", "故障排除")}
          </h2>

          <QA q={t(
            "Alpha research is stuck at '2/24 factors' and won't progress. What's wrong?",
            "Alpha 研究卡在 '2/24 factors' 不再前進。怎麼回事？"
          )}>
            <p className="mb-2">
              {t(
                "This is almost always caused by Yahoo Finance rate limiting. The alpha pipeline computes 24 factors, each requiring price data for every stock in your universe. When Yahoo detects too many rapid requests, it throttles your connection. The system will retry automatically with exponential backoff, but this can take several minutes for large universes.",
                "這幾乎總是由 Yahoo Finance 速率限制引起的。Alpha 管線計算 24 個因子，每個因子都需要您投資範圍中每檔股票的價格數據。當 Yahoo 偵測到過多快速請求時，會限制您的連接。系統會自動以指數退避重試，但對於大型投資範圍，這可能需要幾分鐘。"
              )}
            </p>
            <p className="mb-2">
              {t(
                "Solutions: (1) Reduce your universe size to 20-30 stocks for initial research. (2) Wait — the system will eventually complete. (3) Run a second time — cached data makes subsequent runs much faster. (4) Switch to FinMind for Taiwan stocks, which has more generous rate limits with an API token.",
                "解決方案：(1) 將投資範圍縮小到 20-30 檔股票進行初步研究。(2) 等待 — 系統最終會完成。(3) 再執行一次 — 快取數據使後續執行更快。(4) 台股改用 FinMind，使用 API 令牌有更寬鬆的速率限制。"
              )}
            </p>
          </QA>

          <QA q={t(
            "My backtest completed with 0 trades. What went wrong?",
            "我的回測完成後有 0 筆交易。哪裡出錯了？"
          )}>
            <p className="mb-2">
              {t(
                "Zero trades usually means the strategy never generated non-zero target weights. Common causes:",
                "零交易通常意味著策略從未產生非零的目標權重。常見原因："
              )}
            </p>
            <ul className="list-disc list-inside mb-2 space-y-1">
              <li>{t("Date range too short — momentum and MA strategies need a warm-up period (e.g., 200 bars for a 200-day MA). If your backtest period is shorter than the warm-up, no signals are generated.", "日期範圍太短 — 動量和均線策略需要暖機期間（例如 200 日均線需要 200 根 K 棒）。如果回測期間短於暖機期，不會產生訊號。")}</li>
              <li>{t("Invalid ticker symbols — check that your universe tickers are correct. Taiwan stocks need the .TW suffix (e.g., 2330.TW, not 2330).", "無效的股票代碼 — 確認您的投資範圍代碼正確。台股需要 .TW 後綴（例如 2330.TW，而非 2330）。")}</li>
              <li>{t("Strategy parameters too restrictive — for RSI Oversold, RSI rarely drops below 30 in strong bull markets. For Mean Reversion, the z-score threshold may be too extreme.", "策略參數過於嚴格 — 對於 RSI 超賣策略，在強勢多頭市場中 RSI 很少跌破 30。對於均值回歸，z-score 閾值可能太極端。")}</li>
              <li>{t("No data for the selected period — verify data exists by checking the backtest date range against the stock's listing date.", "所選期間沒有數據 — 通過檢查回測日期範圍與股票上市日期來驗證數據是否存在。")}</li>
            </ul>
          </QA>

          <QA q={t(
            "Paper trading shows 'disconnected' status. How do I fix it?",
            "模擬交易顯示 '已斷線' 狀態。如何修復？"
          )}>
            <p className="mb-2">
              {t(
                "Check the following in order:",
                "按順序檢查以下項目："
              )}
            </p>
            <ol className="list-decimal list-inside mb-2 space-y-1">
              <li>{t("Verify QUANT_MODE=paper is set in your .env file (not 'backtest' which is the default).", "確認 .env 檔案中設定了 QUANT_MODE=paper（而非預設的 'backtest'）。")}</li>
              <li>{t("Check that QUANT_SINOPAC_API_KEY and QUANT_SINOPAC_SECRET are correctly set — no extra spaces or quotes.", "確認 QUANT_SINOPAC_API_KEY 和 QUANT_SINOPAC_SECRET 已正確設定 — 沒有多餘的空格或引號。")}</li>
              <li>{t("Verify the CA certificate path (QUANT_SINOPAC_CA_PATH) points to a valid .p12 file and the password is correct.", "確認 CA 憑證路徑（QUANT_SINOPAC_CA_PATH）指向有效的 .p12 檔案且密碼正確。")}</li>
              <li>{t("Ensure you restarted the backend after changing .env values.", "確保更改 .env 值後已重啟後端。")}</li>
              <li>{t("Check if the market is open — Sinopac's paper trading server may not be available outside market hours.", "檢查市場是否開盤 — 永豐金的模擬交易伺服器可能在非交易時間不可用。")}</li>
            </ol>
          </QA>

          <QA q={t(
            "Charts show incorrect dates or appear shifted. What's going on?",
            "圖表顯示不正確的日期或看起來有偏移。怎麼回事？"
          )}>
            <p className="mb-2">
              {t(
                "This is typically a data cache issue. The system normalizes all dates to timezone-naive UTC, but stale cached data from a previous version may have timezone-aware timestamps that cause display misalignment.",
                "這通常是數據快取問題。系統將所有日期標準化為時區無關的 UTC，但來自先前版本的過期快取數據可能有帶時區的時間戳，導致顯示偏移。"
              )}
            </p>
            <p className="mb-2">
              {t(
                "Solution: Clear the Parquet cache files and re-run your backtest. The fresh download will have properly normalized timestamps. If the issue persists, check your browser's timezone settings — the frontend renders dates in your local timezone, which may differ from the data's UTC base.",
                "解決方案：清除 Parquet 快取檔案並重新執行回測。重新下載的數據會有正確標準化的時間戳。如果問題持續，檢查瀏覽器的時區設定 — 前端以您的本地時區渲染日期，可能與數據的 UTC 基準不同。"
              )}
            </p>
          </QA>

          <QA q={t(
            "How do I enable paper trading mode?",
            "如何啟用模擬交易模式？"
          )}>
            <p className="mb-2">
              {t(
                "Paper trading requires three configuration steps:",
                "模擬交易需要三個配置步驟："
              )}
            </p>
            <ol className="list-decimal list-inside mb-2 space-y-1">
              <li>
                {t("Set ", "設定 ")}
                <code className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">QUANT_MODE=paper</code>
                {t(" in your .env file. The default mode is 'backtest' which only runs historical simulations.", " 在您的 .env 檔案中。預設模式為 'backtest'，僅運行歷史模擬。")}
              </li>
              <li>
                {t(
                  "Configure broker credentials (see the Broker Setup section above for Sinopac/Shioaji setup).",
                  "配置券商憑證（請參閱上方的券商設定章節了解永豐金/Shioaji 設定）。"
                )}
              </li>
              <li>
                {t(
                  "Restart the backend server. It will connect to the broker's paper trading environment automatically. You can verify the connection status on the Dashboard page or via GET /api/v1/system/health.",
                  "重啟後端伺服器。它會自動連接到券商的模擬交易環境。您可以在儀表板頁面或通過 GET /api/v1/system/health 驗證連接狀態。"
                )}
              </li>
            </ol>
            <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-3 text-sm text-blue-700 dark:text-blue-300 mt-2">
              <span className="font-semibold">{t("Tip: ", "提示：")}</span>
              {t(
                "You can run the built-in SimBroker (simulated broker) without any broker credentials by keeping QUANT_MODE=backtest. SimBroker simulates fills with configurable slippage and is useful for strategy development before connecting to a real broker.",
                "您可以保持 QUANT_MODE=backtest，無需任何券商憑證即可使用內建的 SimBroker（模擬券商）。SimBroker 以可配置的滑價模擬成交，在連接真實券商之前對策略開發很有用。"
              )}
            </div>
          </QA>
        </div>
      )}
    </div>
  );
}
