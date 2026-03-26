import { useT } from "@core/i18n";

export function ChapterPaperTrading({ section }: { section?: string }) {
  const { lang } = useT();
  const t = (en: string, zh: string) => (lang === "zh" ? zh : en);

  return (
    <div className="space-y-2">
      {/* ── Section: research-to-trade ── */}
      {(!section || section === "research-to-trade") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("From Research to Live Trading", "從研究到實盤交易")}
          </h2>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("The Four-Stage Workflow", "四階段工作流程")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Every strategy should pass through four stages before risking real capital. Skipping stages is the most common mistake individual investors make.",
              "每個策略在投入真實資金之前都應經過四個階段。跳過階段是個人投資者最常犯的錯誤。"
            )}
          </p>
          <ol className="list-decimal list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-2">
            <li>
              <span className="font-semibold">{t("Alpha Research", "Alpha 研究")}</span>{" "}
              — {t(
                "Explore factor signals, compute IC/IR, identify which factors predict returns in your universe.",
                "探索因子訊號、計算 IC/IR，找出哪些因子能預測您投資範圍中的報酬。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Backtest", "回測")}</span>{" "}
              — {t(
                "Run historical simulations with realistic costs, slippage, and risk constraints. Walk-forward analysis adds out-of-sample rigor.",
                "使用真實的成本、滑價和風險限制進行歷史模擬。前推分析增加樣本外的嚴謹性。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Paper Trading", "模擬交易")}</span>{" "}
              — {t(
                "Execute the strategy against live market data with zero real money. This reveals issues backtests cannot: API latency, order rejections, data gaps, and timing problems.",
                "使用即時市場數據執行策略，但不投入真實資金。這會揭露回測無法發現的問題：API 延遲、訂單被拒、數據缺口和時序問題。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Live Trading", "實盤交易")}</span>{" "}
              — {t(
                "Deploy with real capital only after paper trading validates the strategy.",
                "只有在模擬交易驗證策略後，才投入真實資金。"
              )}
            </li>
          </ol>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Why Paper Trading Matters", "為什麼模擬交易很重要")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Backtests are idealized. They assume perfect fills at close prices, no API errors, no broker downtime, and no emotional interference. Paper trading exposes the gap between theory and reality:",
              "回測是理想化的。它們假設以收盤價完美成交、沒有 API 錯誤、沒有券商停機，也沒有情緒干擾。模擬交易揭露了理論與現實之間的差距："
            )}
          </p>
          <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
            <li>{t("Order fills may differ from expected prices (slippage)", "訂單成交價可能與預期價格不同（滑價）")}</li>
            <li>{t("Data feeds can have delays or gaps during volatile markets", "在波動劇烈的市場中，數據源可能有延遲或缺口")}</li>
            <li>{t("Broker APIs may reject orders due to lot size, price limits, or margin", "券商 API 可能因為整股限制、價格限制或保證金而拒絕訂單")}</li>
            <li>{t("Strategy rebalancing timing may conflict with market hours", "策略再平衡時間可能與市場交易時間衝突")}</li>
            <li>{t("Network issues can cause missed signals or duplicate orders", "網路問題可能導致錯過訊號或重複下單")}</li>
          </ul>

          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
            <span className="font-semibold">{t("Recommendation: ", "建議：")}</span>
            {t(
              "Run paper trading for a minimum of 4 weeks (roughly 20 trading days). This covers at least one full rebalancing cycle and exposes the strategy to varied market conditions.",
              "模擬交易至少執行 4 週（約 20 個交易日）。這至少涵蓋一個完整的再平衡週期，並讓策略經歷各種市場狀況。"
            )}
          </div>
        </div>
      )}

      {/* ── Section: broker-setup ── */}
      {(!section || section === "broker-setup") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("Broker Setup (Shioaji / Sinopac)", "券商設定（Shioaji / 永豐金）")}
          </h2>

          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "For Taiwan market paper and live trading, the system integrates with Sinopac Securities via the Shioaji SDK. Follow these steps to configure your environment:",
              "對於台灣市場的模擬與實盤交易，系統透過 Shioaji SDK 與永豐金證券整合。請按照以下步驟配置您的環境："
            )}
          </p>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Step 1: Open a Sinopac Account", "步驟一：開立永豐金帳戶")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Open a securities account at Sinopac Securities. You will need your national ID, a bank account for settlement, and to enable electronic trading (eService).",
              "在永豐金證券開立證券帳戶。您需要身分證、用於交割的銀行帳戶，並開啟電子交易（eService）。"
            )}
          </p>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Step 2: Get API Credentials", "步驟二：取得 API 憑證")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Log in to the Sinopac API portal and generate an API key and secret. These are separate from your trading password.",
              "登入永豐金 API 入口網站並產生 API 金鑰和密鑰。這些與您的交易密碼不同。"
            )}
          </p>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Step 3: Download CA Certificate", "步驟三：下載 CA 憑證")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Download the personal CA certificate from the Sinopac eService portal. This certificate is required for order placement and must be renewed annually.",
              "從永豐金 eService 入口網站下載個人 CA 憑證。此憑證是下單所必需的，且必須每年更新。"
            )}
          </p>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Step 4: Configure Environment Variables", "步驟四：配置環境變數")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Add the following to your .env file:",
              "將以下內容添加到您的 .env 檔案："
            )}
          </p>
          <pre className="bg-slate-100 dark:bg-surface-light rounded-lg p-4 text-xs font-mono text-slate-700 dark:text-slate-300 mb-4 overflow-x-auto">
{`QUANT_MODE=paper
QUANT_SINOPAC_API_KEY=your_api_key_here
QUANT_SINOPAC_SECRET=your_secret_here
QUANT_SINOPAC_CA_PATH=/path/to/your/ca_cert.p12
QUANT_SINOPAC_CA_PASSWORD=your_ca_password`}
          </pre>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Step 5: Restart the Backend", "步驟五：重啟後端")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Restart the backend server so it picks up the new configuration. The system will automatically connect to Sinopac's paper trading environment when QUANT_MODE=paper.",
              "重啟後端伺服器以載入新的配置。當 QUANT_MODE=paper 時，系統會自動連接到永豐金的模擬交易環境。"
            )}
          </p>

          <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
            <span className="font-semibold">{t("Warning: ", "警告：")}</span>
            {t(
              "Never commit your .env file to version control. API keys and CA passwords are sensitive credentials.",
              "永遠不要將 .env 檔案提交到版本控制。API 金鑰和 CA 密碼是敏感憑證。"
            )}
          </div>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Taiwan Market Hours", "台灣市場交易時間")}
          </h3>
          <div className="overflow-x-auto mb-4">
            <table className="w-full text-sm text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded">
              <thead>
                <tr className="bg-slate-50 dark:bg-surface-light">
                  <th className="text-left p-2 font-semibold">{t("Session", "時段")}</th>
                  <th className="text-left p-2 font-semibold">{t("Hours (Local)", "時間（台北）")}</th>
                  <th className="text-left p-2 font-semibold">{t("Notes", "備註")}</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-slate-200 dark:border-slate-700">
                  <td className="p-2">{t("Regular Session", "一般交易")}</td>
                  <td className="p-2 font-mono">09:00 – 13:30</td>
                  <td className="p-2">{t("Main trading window", "主要交易時段")}</td>
                </tr>
                <tr className="border-t border-slate-200 dark:border-slate-700">
                  <td className="p-2">{t("After-Hours (Fixed Price)", "盤後定價")}</td>
                  <td className="p-2 font-mono">14:00 – 14:30</td>
                  <td className="p-2">{t("Trades at closing price", "以收盤價交易")}</td>
                </tr>
                <tr className="border-t border-slate-200 dark:border-slate-700">
                  <td className="p-2">{t("Futures Day Session", "期貨日盤")}</td>
                  <td className="p-2 font-mono">08:45 – 13:45</td>
                  <td className="p-2">{t("Index & stock futures", "指數與股票期貨")}</td>
                </tr>
                <tr className="border-t border-slate-200 dark:border-slate-700">
                  <td className="p-2">{t("Futures Night Session", "期貨夜盤")}</td>
                  <td className="p-2 font-mono">15:00 – 05:00</td>
                  <td className="p-2">{t("Next day, selected products", "隔日，部分商品")}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Section: monitoring ── */}
      {(!section || section === "monitoring") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("Monitoring & Going Live", "監控與上線")}
          </h2>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("What to Monitor During Paper Trading", "模擬交易期間的監控項目")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Paper trading is not a set-and-forget exercise. Actively monitor these metrics daily:",
              "模擬交易不是設定後就不管的作業。每天主動監控以下指標："
            )}
          </p>
          <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
            <li>
              <span className="font-semibold">{t("NAV Tracking", "淨值追蹤")}</span>
              {" — "}{t(
                "Compare paper NAV curve against what your backtest predicted. Divergence reveals model assumptions that don't hold in practice.",
                "將模擬淨值曲線與回測預測進行比較。差異揭示了在實踐中不成立的模型假設。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Fill Rates", "成交率")}</span>
              {" — "}{t(
                "What percentage of orders are filled? Partial fills and rejections indicate liquidity or pricing issues.",
                "有多少百分比的訂單成交？部分成交和拒絕表示流動性或定價問題。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Queued / Pending Orders", "排隊中/待處理訂單")}</span>
              {" — "}{t(
                "Orders stuck in pending state may indicate API connectivity issues or order validation failures.",
                "卡在待處理狀態的訂單可能表示 API 連接問題或訂單驗證失敗。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Daily Reconciliation", "每日對帳")}</span>
              {" — "}{t(
                "The system's internal position state should match the broker's reported positions. Any mismatch is a critical bug that must be resolved before going live.",
                "系統內部的持倉狀態應與券商報告的持倉一致。任何不一致都是必須在上線前解決的嚴重錯誤。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Risk Rule Triggers", "風控規則觸發")}</span>
              {" — "}{t(
                "Monitor how often risk rules block trades. Frequent triggers may mean your strategy needs recalibration.",
                "監控風控規則阻止交易的頻率。頻繁觸發可能意味著您的策略需要重新校準。"
              )}
            </li>
          </ul>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Go-Live Checklist", "上線檢查清單")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Only transition to live trading when ALL of the following conditions are met:",
              "只有在滿足以下所有條件時才轉為實盤交易："
            )}
          </p>
          <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
            <li>{t("At least 4 weeks (20 trading days) of paper trading completed", "至少完成 4 週（20 個交易日）的模擬交易")}</li>
            <li>{t("Paper Sharpe ratio is within 70% of backtest Sharpe (e.g., backtest Sharpe = 1.5 → paper Sharpe ≥ 1.05)", "模擬夏普比率在回測夏普比率的 70% 以內（例如回測夏普 = 1.5 → 模擬夏普 ≥ 1.05）")}</li>
            <li>{t("No unresolved reconciliation discrepancies", "沒有未解決的對帳差異")}</li>
            <li>{t("Risk rules are properly configured and tested", "風控規則已正確配置並測試")}</li>
            <li>{t("Kill switch has been tested (trigger and recovery)", "熔斷機制已測試（觸發和恢復）")}</li>
            <li>{t("Notification channels (Discord/LINE/Telegram) are set up and confirmed working", "通知管道（Discord/LINE/Telegram）已設定並確認正常運作")}</li>
          </ul>

          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
            <span className="font-semibold">{t("Tip: ", "提示：")}</span>
            {t(
              "When going live, start with 50% of your intended allocation. Scale up to full size after 2 additional weeks if performance remains consistent.",
              "上線時，從您預期配置的 50% 開始。如果績效保持一致，2 週後再擴大到完整規模。"
            )}
          </div>

          <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
            <span className="font-semibold">{t("Warning: ", "警告：")}</span>
            {t(
              "To switch to live trading, change QUANT_MODE=live in your .env file. This is irreversible during a trading session — the system will place real orders immediately. Double-check all settings before restarting.",
              "要切換到實盤交易，請在 .env 檔案中更改 QUANT_MODE=live。在交易時段內這是不可逆的 — 系統會立即下真實訂單。重啟前請再三確認所有設定。"
            )}
          </div>
        </div>
      )}
    </div>
  );
}
