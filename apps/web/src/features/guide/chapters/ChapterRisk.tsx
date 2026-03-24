import { useT } from "@core/i18n";

export function ChapterRisk({ section }: { section?: string }) {
  const { lang } = useT();
  const t = (en: string, zh: string) => (lang === "zh" ? zh : en);

  return (
    <div className="space-y-2">
      {/* ── Section: why-risk-rules ── */}
      {(!section || section === "why-risk-rules") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("Why Risk Rules Matter", "為什麼風控規則重要")}
          </h2>

          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Risk management is not optional — it is the single most important component of any trading system. History is filled with cautionary tales of what happens without it.",
              "風險管理不是可選的 — 它是任何交易系統中最重要的組件。歷史上充滿了沒有風控的慘痛教訓。"
            )}
          </p>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Knight Capital: $440M in 45 Minutes", "Knight Capital：45 分鐘虧損 4.4 億美元")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "On August 1, 2012, Knight Capital Group deployed a software update that accidentally activated old test code. The system flooded the market with millions of erroneous orders in 45 minutes, resulting in a $440 million loss. The company was bankrupt within days. A simple kill switch — automatically halting trading when losses exceed a threshold — would have limited the damage to a fraction of that amount.",
              "2012 年 8 月 1 日，Knight Capital Group 部署了一個軟體更新，意外啟動了舊的測試程式碼。系統在 45 分鐘內向市場發送了數百萬筆錯誤訂單，造成 4.4 億美元的損失。該公司在幾天內破產。一個簡單的熔斷機制 — 當損失超過閾值時自動停止交易 — 就能將損失限制在很小的範圍。"
            )}
          </p>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("LTCM: When Genius Failed", "LTCM：天才也會失敗")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Long-Term Capital Management had two Nobel laureates and the brightest minds on Wall Street. Their models worked perfectly — until they didn't. Excessive leverage (25:1) combined with correlated positions led to a $4.6 billion loss in 1998 that nearly destabilized global financial markets. Position sizing limits and leverage caps are not constraints on profit — they are insurance against ruin.",
              "長期資本管理公司有兩位諾貝爾獎得主和華爾街最聰明的人才。他們的模型完美運作 — 直到失效為止。過度槓桿（25:1）加上相關聯的部位導致 1998 年 46 億美元的損失，幾乎動搖了全球金融市場。部位規模限制和槓桿上限不是對利潤的約束 — 而是防止破產的保險。"
            )}
          </p>

          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
            <span className="font-semibold">{t("Core Philosophy: ", "核心理念：")}</span>
            {t(
              "It is always better to miss a profitable trade than to take a catastrophic loss. You can recover from missed opportunities; you cannot recover from a blown-up account.",
              "錯過一筆盈利交易永遠比承受災難性損失好。您可以從錯失的機會中恢復；但無法從爆倉的帳戶中恢復。"
            )}
          </div>
        </div>
      )}

      {/* ── Section: rules-explained ── */}
      {(!section || section === "rules-explained") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("Risk Rules Explained", "風控規則詳解")}
          </h2>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "The system provides 10 declarative risk rules. Each rule is a pure function that evaluates an order and returns APPROVE, WARN, or REJECT. Rules are evaluated sequentially — the first REJECT stops the order immediately.",
              "系統提供 10 條宣告式風控規則。每條規則都是一個純函數，評估訂單並回傳 APPROVE、WARN 或 REJECT。規則按順序評估 — 第一個 REJECT 會立即停止訂單。"
            )}
          </p>

          {/* Rule 1 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("1. Max Position Weight", "1. 最大持倉權重")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Limits any single position to a maximum percentage of total portfolio NAV. Default: 10%. This prevents over-concentration in a single name. If an order would push a position above this threshold, it is rejected.",
              "限制任何單一持倉佔總投資組合淨值的最大百分比。預設：10%。這防止過度集中於單一標的。如果一筆訂單會使持倉超過此閾值，該訂單將被拒絕。"
            )}
          </p>

          {/* Rule 2 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("2. Max Order Notional", "2. 最大訂單名義金額")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Caps the dollar value of any single order relative to portfolio NAV. Default: 10%. Prevents accidentally placing an order that is disproportionately large. This is your first line of defense against fat-finger errors in order size.",
              "限制任何單筆訂單相對於投資組合淨值的金額。預設：10%。防止意外下達不成比例的大額訂單。這是您防止訂單大小錯誤的第一道防線。"
            )}
          </p>

          {/* Rule 3 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("3. Daily Drawdown", "3. 每日最大回撤")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Monitors the portfolio's intraday loss from the day's peak NAV. Three severity levels:",
              "監控投資組合從當日淨值高點的日內損失。三個嚴重程度："
            )}
          </p>
          <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
            <li><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">2%</span> — {t("Warning: logs alert, sends notification", "警告：記錄警報，發送通知")}</li>
            <li><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">3%</span> — {t("Critical: blocks new buy orders, allows sells only", "嚴重：阻止新買入訂單，僅允許賣出")}</li>
            <li><span className="font-mono bg-slate-100 dark:bg-surface-light px-1.5 py-0.5 rounded text-xs">5%</span> — {t("Kill: triggers automatic kill switch (see below)", "熔斷：觸發自動熔斷機制（見下方）")}</li>
          </ul>

          {/* Rule 4 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("4. Fat Finger Check", "4. 胖手指檢查")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Rejects orders where the limit price deviates more than 5% from the current market price. This catches common data entry errors — typing 1000 instead of 100, or misplacing a decimal point. Applies to limit orders only; market orders are checked by other rules.",
              "拒絕限價與當前市價偏差超過 5% 的訂單。這能捕捉常見的輸入錯誤 — 輸入 1000 而非 100，或小數點位置錯誤。僅適用於限價單；市價單由其他規則檢查。"
            )}
          </p>

          {/* Rule 5 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("5. Max Daily Trades", "5. 每日最大交易次數")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Limits the total number of trades per day. Default: 100. This prevents runaway algorithms from generating thousands of trades due to bugs or unexpected market conditions. For most strategies, 100 trades per day is extremely generous.",
              "限制每日交易總次數。預設：100 次。這防止失控的演算法因程式錯誤或意外市場狀況而產生數千筆交易。對大多數策略而言，每日 100 筆交易已經非常寬裕。"
            )}
          </p>

          {/* Rule 6 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("6. Order vs Average Daily Volume (ADV)", "6. 訂單與平均日成交量比較")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Rejects orders whose size exceeds a percentage of the stock's average daily volume. Default: 10% of ADV. Trading too large relative to volume causes market impact — your own orders move the price against you. This is especially important for small-cap Taiwan stocks with limited liquidity.",
              "拒絕訂單量超過該股票平均日成交量一定百分比的訂單。預設：ADV 的 10%。相對於成交量交易過大會造成市場衝擊 — 您自己的訂單會使價格對您不利。這對流動性有限的台灣小型股特別重要。"
            )}
          </p>

          {/* Rule 7 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("7. Price Circuit Breaker", "7. 價格熔斷器")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Rejects orders when the current price has moved more than 10% from the previous close. This protects against trading during extreme volatility or after erroneous price data. Taiwan stocks already have a 10% daily price limit, but this rule also applies to US stocks and ETFs which have no exchange-imposed limits.",
              "當當前價格相對於前一收盤價移動超過 10% 時拒絕訂單。這防止在極端波動或錯誤價格數據後進行交易。台股已有 10% 漲跌幅限制，但此規則也適用於沒有交易所限制的美股和 ETF。"
            )}
          </p>

          {/* Rule 8 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("8. Max Asset Class Weight", "8. 最大資產類別權重")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Limits exposure to any single asset class (equity, futures, ETF). This enforces diversification at the asset class level. For example, you might cap equity exposure at 70% to ensure at least 30% is allocated to bonds, commodities, or cash.",
              "限制對任何單一資產類別（股票、期貨、ETF）的曝險。這在資產類別層面強制實施分散化。例如，您可以將股票曝險上限設為 70%，以確保至少 30% 配置於債券、商品或現金。"
            )}
          </p>

          {/* Rule 9 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("9. Max Currency Exposure", "9. 最大貨幣曝險")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Limits exposure to any single foreign currency. Since the system supports both TWD and USD assets, unhedged currency exposure adds risk that is not compensated by your alpha signals. This rule ensures you don't accidentally take on excessive FX risk by over-allocating to US-denominated assets.",
              "限制對任何單一外幣的曝險。由於系統同時支援 TWD 和 USD 資產，未避險的貨幣曝險增加了不被您的 alpha 訊號補償的風險。此規則確保您不會因過度配置美元計價資產而意外承擔過多的匯率風險。"
            )}
          </p>

          {/* Rule 10 */}
          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("10. Max Gross Leverage", "10. 最大總槓桿")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "Caps the total gross exposure (sum of absolute position values) relative to NAV. Default: 1.5x. A portfolio with 100% long and 50% short has 1.5x gross leverage. This prevents excessive leverage that amplifies both gains and losses. Remember LTCM: leverage is what turns a bad trade into a fatal one.",
              "限制總毛曝險（持倉絕對值之和）相對於淨值的比率。預設：1.5 倍。一個 100% 多頭和 50% 空頭的投資組合具有 1.5 倍總槓桿。這防止過度槓桿放大收益和損失。記住 LTCM：槓桿是將壞交易變成致命交易的因素。"
            )}
          </p>

          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
            <span className="font-semibold">{t("Tip: ", "提示：")}</span>
            {t(
              "You can view and toggle all risk rules on the Risk page. Rules can be configured per-strategy or globally. Start with the defaults — they are conservative by design.",
              "您可以在風控頁面查看和切換所有風控規則。規則可以按策略或全局配置。從預設值開始 — 它們的設計本身就是保守的。"
            )}
          </div>
        </div>
      )}

      {/* ── Section: kill-switch ── */}
      {(!section || section === "kill-switch") && (
        <div>
          <h2 className="text-xl font-bold mb-4 text-slate-900 dark:text-slate-100">
            {t("Kill Switch", "熔斷機制")}
          </h2>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("How It Triggers", "觸發方式")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "The kill switch can be triggered in two ways:",
              "熔斷機制可以通過兩種方式觸發："
            )}
          </p>
          <ul className="list-disc list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
            <li>
              <span className="font-semibold">{t("Automatic", "自動")}</span>
              {" — "}{t(
                "Triggered when daily drawdown reaches 5%. No human intervention required.",
                "當每日回撤達到 5% 時觸發。不需要人工干預。"
              )}
            </li>
            <li>
              <span className="font-semibold">{t("Manual", "手動")}</span>
              {" — "}{t(
                "Any user with the risk_manager role (or above) can activate it via the Risk page or the API endpoint POST /api/v1/risk/kill-switch.",
                "任何具有 risk_manager 角色（或更高）的使用者可以通過風控頁面或 API 端點 POST /api/v1/risk/kill-switch 啟動。"
              )}
            </li>
          </ul>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("What Happens When It Triggers", "觸發後會發生什麼")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "When the kill switch activates, the system takes immediate action:",
              "當熔斷機制啟動時，系統立即採取行動："
            )}
          </p>
          <ol className="list-decimal list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-1">
            <li>{t("All running strategies are stopped immediately", "所有運行中的策略立即停止")}</li>
            <li>{t("All pending orders are cancelled", "所有待處理訂單被取消")}</li>
            <li>{t("Market sell orders are placed for all open positions", "對所有持倉下達市價賣出訂單")}</li>
            <li>{t("Notifications are sent via all configured channels", "通過所有已配置的管道發送通知")}</li>
            <li>{t("The system enters a locked state — no new orders can be placed", "系統進入鎖定狀態 — 無法下新訂單")}</li>
          </ol>

          <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300 mb-4">
            <span className="font-semibold">{t("Warning: ", "警告：")}</span>
            {t(
              "Positions are closed at market price. During volatile markets, market orders may fill at significantly worse prices than expected. This is the cost of emergency risk reduction — it is still better than allowing unlimited losses.",
              "持倉以市價平倉。在波動劇烈的市場中，市價單的成交價可能明顯差於預期。這是緊急風險降低的代價 — 仍然比允許無限損失好。"
            )}
          </div>

          <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-800 dark:text-slate-200">
            {t("Recovery After Kill Switch", "熔斷後的恢復")}
          </h3>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 mb-4">
            {t(
              "The kill switch is deliberately difficult to reverse. This is by design — it forces you to pause, investigate, and think before resuming trading.",
              "熔斷機制的解除是刻意設計得較困難的。這是設計理念 — 它迫使您在恢復交易前暫停、調查和思考。"
            )}
          </p>
          <ol className="list-decimal list-inside text-sm text-slate-600 dark:text-slate-400 mb-4 space-y-2">
            <li>{t("Review what caused the drawdown — was it a strategy bug, market event, or data error?", "檢討造成回撤的原因 — 是策略錯誤、市場事件還是數據錯誤？")}</li>
            <li>{t("Fix any identified issues (update strategy parameters, patch bugs, etc.)", "修復已識別的問題（更新策略參數、修補錯誤等）")}</li>
            <li>{t("A risk_manager must manually deactivate the kill switch via the Risk page", "risk_manager 必須通過風控頁面手動解除熔斷")}</li>
            <li>{t("Strategies must be manually restarted — they do not auto-resume", "策略必須手動重啟 — 不會自動恢復")}</li>
          </ol>

          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300 mb-4">
            <span className="font-semibold">{t("Tip: ", "提示：")}</span>
            {t(
              "Test the kill switch during paper trading. Trigger it intentionally, verify that positions close and notifications fire, then practice the recovery procedure. You don't want the first time you use it to be during a real emergency.",
              "在模擬交易期間測試熔斷機制。故意觸發它，驗證持倉是否平倉及通知是否發送，然後練習恢復程序。您不會希望第一次使用它是在真正的緊急情況下。"
            )}
          </div>
        </div>
      )}
    </div>
  );
}
