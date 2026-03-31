# Autoresearch Status Report

> Updated: 2026-04-01 06:16:03

## Dashboard

| Item | Value |
|------|-------|
| Agent | Running (Up About an hour) |
| Evaluator | Running (Up 2 hours (healthy)) |
| Watchdog | Running (Up 2 hours) |
| Experiments | 440 |
| Keep / Discard / Crash | 0 / 440 / 0 |
| Level Distribution | L0:0 L1:219 L2:221 L3:0 L4:0 L5:0 |
| Deployed | 0 |
| Factor-Level PBO | N/A |
| ICIR Method | Method D (median \|ICIR\| ??0.30) |
| Best Score | 0 |
| Best Factor | N/A |

## Experiments (latest first)

| Score | ICIR | Level | Status | Description |
|------:|-----:|-------|--------|-------------|
| none | none | L1 | discard | CAPM alpha: Jensen's alpha from market regression 240d. |
| none | none | L1 | discard | Rolling VWAP deviation trend: close vs cumulative VWAP slope 120d. |
| weak | weak | L2 | discard | CAPM alpha: time-series intercept vs equal-weighted market 240d. |
| weak | weak | L2 | discard | Size-vol residual alpha: return after removing size and vol effects. |
| weak | weak | L2 | discard | Size-vol residual alpha: return after removing size and volatility effects. |
| weak | weak | L2 | discard | Cross-sectional residual alpha: return orthogonal to market and vol. |
| none | none | L1 | discard | Cross-sectional residual alpha: return orthogonal to market and vol. |
| none | none | L2 | discard | DMI trend quality: average of daily DMI balance EMA-smoothed 120d. |
| none | none | L2 | discard | Negative ATR compression ratio: recent vs historical volatility 240d. |
| weak | weak | L2 | discard | Negative volatility ratio: recent vs historical ATR compression 240d. |
| weak | weak | L2 | discard | DMI trend quality: mean of daily DMI balance EMA-smoothed 120d. |
| none | none | L1 | discard | High-volume day momentum: avg return on top-quartile volume days 120d. |
| none | none | L1 | discard | Foreign-trust agreement days: fraction of days both buy net 120d. |
| none | none | L2 | discard | Foreign-trust agreement days: fraction of days both buy net 120d. |
| none | none | L1 | discard | Negative volume-weighted volatility: informed-day risk measure 240d. |
| none | none | L1 | discard | Gap continuation: correlation of overnight gaps with intraday moves 120d. |
| weak | weak | L2 | discard | Gap continuation: correlation of overnight gaps with intraday moves 120d. |
| none | none | L1 | discard | Cumulative foreign ownership proxy: total net foreign buying to date. |
| none | none | L1 | discard | Momentum-neutral trend quality: Kendall tau orthogonalized to return. |
| weak | weak | L2 | discard | MACD momentum signal: EMA12 vs EMA26 with 120d warmup. |
| weak | weak | L2 | discard | SMA10 dominance: fraction of days close above 10-day SMA over 240d. |
| none | none | L1 | discard | SMA10 dominance: fraction of days close > 10-day SMA over 240d. |
| none | none | L1 | discard | MACD histogram: EMA12 minus EMA26 normalized by price. |
| none | none | L1 | discard | MACD histogram: EMA12 minus EMA26 normalized by price. |
| none | none | L1 | discard | Midpoint momentum: trend in high-low midpoint skip close noise 240d. |
| none | none | L1 | discard | Overnight dominance: fraction of absolute return from overnight gaps 120d. |
| none | none | L1 | discard | Trimmed mean momentum: average daily return excluding extreme days 240d. |
| weak | weak | L2 | discard | Trimmed mean momentum: average daily return excluding extreme days 240d. |
| weak | weak | L2 | discard | Confirmed trend: DMI balance times Kendall tau product 240d. |
| weak | weak | L2 | discard | Confirmed trend: DMI balance × Kendall tau product 240d. |
| weak | weak | L2 | discard | 120-day range position: where close sits in its own high-low range. |
| weak | weak | L2 | discard | 120-day range position: where close sits in its own high-low range. |
| none | none | L1 | discard | Dollar volume trend: increasing trading interest over 120 days. |
| none | none | L1 | discard | Directional movement balance: +DI minus -DI averaged over 240d. |
| weak | weak | L2 | discard | EMA directional movement: exponentially weighted +DI/-DI 240d. |
| weak | weak | L2 | discard | Directional movement balance: +DI minus -DI averaged over 240d. |
| weak | weak | L2 | discard | Directional movement balance: +DI minus -DI averaged over 120d. |
| none | none | L2 | discard | Directional movement balance: +DI minus -DI averaged over 120d. |
| none | none | L1 | discard | EMA momentum: exponentially weighted cumulative return 120d halflife 40d. |
| none | none | L1 | discard | Negative volume skewness: consistent non-spiky volume 120d. |
| none | none | L1 | discard | Negative absolute return autocorrelation: pricing efficiency 240d. |
| none | none | L1 | discard | Directional volume ratio: net signed volume vs total volume 120d. |
| none | none | L1 | discard | Cross-sectional relative strength: excess return vs market avg 120d. |
| none | none | L1 | discard | Tail ratio: upside vs downside tail asymmetry of returns 240d. |
| none | none | L1 | discard | Earnings momentum proxy: negative PER change over 120 trading days. |
| none | none | L1 | discard | Long-term reversal: negative 500-day return buy long-term losers. |
| none | none | L1 | discard | Tail ratio: upside vs downside tail asymmetry of returns 240d. |
| none | none | L1 | discard | Foreign flow z-score: recent 20d foreign buying vs own 120d history. |
| weak | weak | L2 | discard | Selling exhaustion: negative price-volume trend correlation 120d. |
| none | none | L2 | discard | Trend linearity: R-squared of log-close regressed on time 120d. |
| none | none | L1 | discard | Price acceleration: second derivative of log price trend 120d. |
| none | none | L2 | discard | Volume-weighted return asymmetry: up-move magnitude vs down-move 120d. |
| none | none | L2 | discard | Negative normalized ATR: low average true range relative to price 120d. |
| none | none | L1 | discard | Volume-weighted momentum: cumulative daily return weighted by relative volume 12 |
| none | none | L1 | discard | Rising floor: trend in daily lows relative to daily highs 240d. |
| none | none | L1 | discard | Rising floor: trend in daily lows relative to daily highs 240d. |
| none | none | L1 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| none | none | L2 | discard | Lower shadow dominance: buying support from intraday lows 120d. |
| none | none | L2 | discard | Lower shadow dominance: buying support from intraday lows 120d. |
| weak | weak | L2 | discard | Trend persistence: fraction of days above own 120d EMA over 240d. |
| none | none | L1 | discard | Negative volatility trend: declining rolling volatility slope 240d. |
| weak | weak | L2 | discard | Trend persistence: fraction of days above own 60d EMA over 120d. |
| none | none | L1 | discard | Down-day recovery: avg next-day return after negative days 240d. |
| none | none | L2 | discard | Volume-regime robust return: min return across volume terciles 120d. |
| none | none | L1 | discard | Peak volume day return: return on highest volume day 240d. |
| none | none | L2 | discard | Inter-event drift: cumulative return on non-event days 240d. |
| none | none | L2 | discard | Overnight return consistency: fraction of positive overnight gaps 240d. |
| weak | weak | L2 | discard | Price trend linearity: R-squared of log-price regression 240d. |
| weak | weak | L2 | discard | Weekly Sharpe ratio: return per risk at weekly aggregation 120d. |
| none | none | L2 | discard | Quiet-day drift: average return on below-median volume days 240d. |
| none | none | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| weak | weak | L2 | discard | Volume-regime robust return: min return across volume terciles 240d. |
| none | none | L2 | discard | Negative weekly return semivariance: downside weekly risk 52w. |
| none | none | L1 | discard | Volume-clock momentum: return over 60 volume-days not calendar-days. |
| none | none | L2 | discard | Asymmetric market capture: upside participation minus downside exposure 240d. |
| none | none | L2 | discard | Opening weakness recovery: stocks opening low but closing high 120d. |
| none | none | L2 | discard | Downside protection breadth: fraction positive on market-down days 240d. |
| none | none | L2 | discard | Downside resistance ratio: stock loss vs market loss on down days 240d. |
| none | none | L1 | discard | Post-volume-surge drift: next-day return after high-volume days 120d. |
| none | none | L1 | discard | Weekly return momentum: 12-week cumulative weekly returns skip 1w. |
| none | none | L1 | discard | EMA momentum with volume confirmation: decay-weighted trend 120d. |
| none | none | L1 | discard | High-volume day return premium: institutional trading direction 120d. |
| none | none | L1 | discard | Up-day volume premium: relative volume on positive vs negative days 240d. |
| none | none | L1 | discard | Cross-sectional size-residual return 240d: pure alpha after size. |
| none | none | L1 | discard | Uptrend momentum: 120d return conditional on above 200d MA. |
| none | none | L1 | discard | Cross-sectional size-residual return 240d: pure alpha after size. |
| none | none | L1 | discard | Volume slope minus price slope divergence: stealth accumulation 240d. |
| none | none | L2 | discard | Lagged volume-return lead-lag cross-predictability 120d. |
| none | none | L2 | discard | Cross-sectional size-residual return: alpha after removing size 120d. |
| none | none | L1 | discard | Cross-sectional size-residual return: alpha after removing size effect 120d. |
| none | none | L1 | discard | Lagged volume-return cross-predictability 120d. |
| none | none | L1 | discard | Negative max consecutive losing days: structural resilience 240d. |
| none | none | L1 | discard | Negative max consecutive losing days: structural resilience 240d. |
| none | none | L1 | discard | Short-minus-long return spread: momentum trajectory change. |
| none | none | L1 | discard | Cumulative trust net buying normalized by volume 240d. |
| none | none | L1 | discard | Higher-high-higher-low trend day fraction over 240d. |
| none | none | L1 | discard | Intraday upside-downside range ratio from open 240d. |
| none | none | L2 | discard | Volume-direction weighted return: accumulation vs distribution 240d. |
| none | none | L2 | discard | Up-day range premium: wider intraday ranges on positive days 240d. |
| none | none | L2 | discard | Close location value averaged over 240d: buying pressure proxy. |
| none | none | L1 | discard | Foreign flow consistency: Sharpe-like ratio of net buying 120d. |
| weak | weak | L2 | discard | Sortino-efficiency product: smooth risk-adjusted momentum 240d. |
| none | none | L1 | discard | Cross-sectional monthly rank persistence: consistent winners 240d. |
| none | none | L2 | discard | Volume-weighted average return minus equal-weighted return 240d. |
| none | none | L2 | discard | Gap continuation ratio: overnight information persistence 240d. |
| weak | weak | L2 | discard | Weekly-scale price path efficiency over 240 trading days. |
| none | none | L1 | discard | Volume-return tail asymmetry: informed buying at price extremes 240d. |
| none | none | L2 | discard | Volume center of mass: recency of trading activity 120d. |
| weak | weak | L2 | discard | Volume center of mass: recency of trading activity 120d. |
| weak | weak | L2 | discard | Calmar ratio: return per maximum drawdown 120d. |
| weak | weak | L2 | discard | Calmar ratio: return per maximum drawdown 120d. |
| none | none | L2 | discard | Quality composite: Sortino ratio + candle body ratio rank average. |
| none | none | L1 | discard | Foreign flow-price divergence: smart money ahead of price. |
| none | none | L2 | discard | Negative range CV: consistent daily price range = stable stocks. |
| none | none | L2 | discard | Quality composite: Sortino ratio + candle body ratio rank average. |
| weak | weak | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| none | none | L1 | discard | Multi-period return consistency: min return across timeframes. |
| none | none | L1 | discard | Multi-scale candle body ratio: stable microstructure quality. |
| none | none | L1 | discard | Revenue growth acceleration: improving earnings momentum. |
| none | none | L1 | discard | Robust momentum: median of rolling 60d returns over 480d. |
| weak | weak | L2 | discard | EMA ratio momentum: smoothed short/long trend signal. |
| none | none | L1 | discard | Robust momentum: median of rolling 60d returns over 480d. |
| none | none | L1 | discard | Cumulative dealer net buying 120d: options hedging flow. |
| none | none | L1 | discard | Cumulative dealer net buying 120d: options hedging flow. |
| none | none | L1 | discard | Negative absolute drift: stocks with near-zero expected return. |
| none | none | L1 | discard | Sortino ratio 240d: stable return per downside risk. |
| weak | weak | L2 | discard | Sortino ratio: return per unit of downside deviation 120d. |
| weak | weak | L2 | discard | Sortino ratio: return per unit of downside deviation 120d. |
| none | none | L2 | discard | Return sign persistence: fraction of same-sign consecutive days. |
| none | none | L2 | discard | Return sign persistence: fraction of same-sign consecutive days. |
| none | none | L1 | discard | Negative price path curvature 240d: decelerating stocks reverse. |
| none | none | L2 | discard | Price path convexity: upward-accelerating price trajectory. |
| none | none | L1 | discard | Closing strength trend: improving close position in daily range. |
| none | none | L1 | discard | Closing strength trend: improving close position in daily range. |
| none | none | L2 | discard | Theil-Sen robust momentum: median pairwise slope of log price. |
| none | none | L1 | discard | Trust investor accumulation intensity over 60 days. |
| none | none | L2 | discard | Theil-Sen robust momentum: median pairwise slope of log price. |
| none | none | L1 | discard | Negative range expansion slope: shrinking daily ranges = stability. |
| none | none | L1 | discard | Negative return-volatility correlation: hedge during stress. |
| none | none | L2 | discard | Negative range-to-volume ratio: range-based market depth. |
| none | none | L2 | discard | Negative range-to-volume ratio: range-based market depth. |
| none | none | L2 | discard | Momentum acceleration: 120d return relative to 500d return. |
| none | none | L1 | discard | Negative monthly return dispersion: consistent performers. |
| weak | weak | L2 | discard | EMA-smoothed candle body ratio 240d: stable microstructure quality. |
| none | none | L1 | discard | Foreign-confirmed overnight return: overnight moves + foreign buying. |
| weak | weak | L2 | discard | EMA-smoothed candle body ratio 240d: stable microstructure quality. |
| weak | weak | L2 | discard | EMA-smoothed candle body ratio 240d: stable microstructure quality. |
| none | none | L1 | discard | 60-day momentum: intermediate-term return continuation. |
| none | none | L1 | discard | Multi-signal composite: body ratio + low vol + min recency. |
| none | none | L1 | discard | Multi-signal composite: body ratio + low vol + min recency. |
| none | none | L1 | discard | Multi-signal composite: body ratio + low vol + min recency. |
| none | none | L1 | discard | Multi-signal composite: body ratio + low vol + min recency. |
| none | none | L2 | discard | Contrarian momentum z-score: buy abnormally weak recent performers. |
| none | none | L2 | discard | Contrarian momentum z-score: buy abnormally weak recent performers. |
| none | none | L2 | discard | Negative MA crossover count: fewer trend changes = cleaner trend. |
| none | none | L1 | discard | Momentum z-score: recent 20d return vs own 240d return distribution. |
| none | none | L2 | discard | Negative MA crossover count: fewer trend changes = cleaner trend. |
| none | none | L2 | discard | Negative cross-sectional rank volatility: stable daily ranking. |
| none | none | L2 | discard | Negative cross-sectional rank volatility: stable daily ranking. |
| none | none | L2 | discard | Negative return magnitude on peak-volume days: deep liquidity. |
| none | none | L2 | discard | Negative return magnitude on peak-volume days: deep liquidity. |
| none | none | L1 | discard | Institutional-confirmed return: momentum on institution-buying days. |
| none | none | L1 | discard | Institutional-confirmed return: momentum on institution-buying days. |
| none | none | L1 | discard | Amihud asymmetry: price impact higher on up days vs down days. |
| none | none | L1 | discard | Amihud asymmetry: price impact higher on up days vs down days. |
| weak | weak | L2 | discard | Recency of minimum: how recently stock hit its 240d low. |
| weak | weak | L2 | discard | Recency of minimum: how recently stock hit its 240d low. |
| none | none | L1 | discard | Recency of maximum: how recently stock hit its 120d high. |
| none | none | L1 | discard | Recency of maximum: how recently stock hit its 120d high. |
| none | none | L2 | discard | Signed intraday drift: avg (close-open)/open captures daily bias. |
| none | none | L1 | discard | Negative Amihud illiquidity change: buy stocks getting more liquid. |
| none | none | L2 | discard | Signed intraday drift: avg (close-open)/open captures daily bias. |
| none | none | L2 | discard | Signed intraday drift: avg (close-open)/open captures daily bias. |
| none | none | L1 | discard | Log price level: high-priced stocks attract institutional capital. |
| none | none | L2 | discard | Log price level: high-priced stocks attract institutional capital. |
| none | none | L2 | discard | Composite: candle body ratio + price delay rank combination. |
| none | none | L2 | discard | Average close location value (CLV): consistent close near daily high. |
| none | none | L2 | discard | 10-day return continuation: short-term momentum at weekly scale. |
| none | none | L1 | discard | 10-day return continuation: short-term momentum at weekly scale. |
| weak | weak | L2 | discard | Candle body ratio 240d: decisive intraday price movement. |
| weak | weak | L2 | discard | Negative candle body ratio: buy stocks with intraday reversal. |
| weak | weak | L2 | discard | Volume surge on positive days: asymmetric volume-return interaction. |
| none | none | L1 | discard | High-volume closing strength: close position on heavy-volume days. |
| none | none | L1 | discard | Candle body ratio: open-close move relative to high-low range. |
| none | none | L1 | discard | Volume surge on positive days: asymmetric volume-return interaction. |
| none | none | L2 | discard | Volume surge on positive days: asymmetric volume-return interaction. |
| none | none | L1 | discard | Return on foreign-buying days: smart money conditional return. |
| none | none | L1 | discard | Negative downside beta: sensitivity to market drops only. |
| none | none | L1 | discard | Negative return distribution entropy: buy predictable stocks. |
| none | none | L2 | discard | Negative downside beta: sensitivity to market drops only. |
| none | none | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| none | none | L1 | discard | Volume-normalized return: total return per unit of cumulative volume. |
| none | none | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| weak | weak | L2 | discard | Negative idiosyncratic volatility from CAPM residuals 240d. |
| weak | weak | L2 | discard | Negative price delay — buy efficiently-priced stocks. |
| weak | weak | L2 | discard | Negative price delay — how quickly stock incorporates market info. |
| none | none | L1 | discard | Implied ROE from PER-PBR rank divergence. |
| none | none | L2 | discard | Negative Garman-Klass volatility estimator 120d. |
| none | none | L1 | discard | Roll implied spread estimator (negative) from return autocovariance. |
| none | none | L2 | discard | Corwin-Schultz high-low spread estimator (negative). |
| none | none | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| none | none | L2 | discard | Momentum consistency: return earned per negative day. |
| none | none | L1 | discard | Foreign buying momentum: acceleration in institutional net purchases. |
| none | none | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| none | none | L1 | discard | Return sign runs test: streaky vs alternating return pattern 120d. |
| none | none | L2 | discard | Dip-buying volume ratio: volume after down vs up days 120d. |
| none | none | L1 | discard | Microstructure quality: body ratio + low extreme frequency 120d. |
| none | none | L1 | discard | Foreign buying consistency: fraction of positive days 60d. |
| none | none | L1 | discard | Negative EMA crossover frequency: trend clarity 120d. |
| none | none | L2 | discard | Average candle body ratio: directional efficiency 240d stable. |
| none | none | L2 | discard | Signed candle body ratio: directional momentum quality 120d. |
| weak | weak | L2 | discard | Average candle body ratio: directional efficiency of daily moves. |
| none | none | L1 | discard | Upside-downside volatility spread: good vs bad risk 120d. |
| none | none | L1 | discard | Closing strength consistency: stable intraday close position 120d. |
| none | none | L1 | discard | Medium-volatility sweet spot: Goldilocks vol zone 120d. |
| none | none | L2 | discard | Volume autocorrelation: persistent institutional trading 120d. |
| none | none | L1 | discard | Negative absolute skewness: return distribution symmetry 120d. |
| none | none | L1 | discard | Weekly return sign consistency: fraction positive weeks 26w. |
| none | none | L2 | discard | Negative overnight gap volatility: stable after-hours pricing 120d. |
| none | none | L2 | discard | Negative volume entropy: concentrated institutional trading 120d. |
| none | none | L1 | discard | High-volume day average return: informed trading direction 120d. |
| none | none | L2 | discard | Gap fill tendency: fraction of overnight gaps reversed intraday. |
| none | none | L2 | discard | Low extreme-move frequency: fewer days with |return| > 3% 120d. |
| none | none | L1 | discard | 7-day momentum: very short-term return continuation. |
| none | none | L1 | discard | 2-year reversal: negative 480d return skip 20d. |
| none | none | L1 | discard | Foreign flow intensity: cumulative foreign_net / avg volume 120d. |
| none | none | L2 | discard | Turning point: recent strength from long-term weakness. |
| none | none | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| none | none | L1 | discard | Volume-lead-return correlation: does volume predict next-day return? |
| none | none | L2 | discard | Negative Amihud: liquidity premium (liquid stocks outperform). |
| none | none | L1 | discard | Log-price trend slope: OLS slope of log(close) over 120d. |
| weak | weak | L2 | discard | Average daily return rank: mean cross-sectional rank over 120d. |
| weak | weak | L2 | discard | Residual mean reversion: negative idiosyncratic return 120d. |
| none | none | L1 | discard | 10-day return reversal: negative recent 10d return. |
| weak | weak | L2 | discard | Quiet breakout: new-high frequency × low volatility composite. |
| weak | weak | L2 | discard | 52-week high frequency: days at 240d high in recent 90 days. |
| weak | weak | L2 | discard | New-high frequency: days at 120d high in recent 60 trading days. |
| none | none | L1 | discard | Tail-trimmed momentum: sum of daily returns ex top/bottom 5, 120d. |
| none | none | L1 | discard | Intraday upside bias: avg (high-open)/(open-low) ratio 120d. |
| none | none | L1 | discard | EMA momentum: exponentially-weighted cumulative return 120d. |
| none | none | L1 | discard | Volume-surprise weighted momentum: return × volume surge signal. |
| none | none | L1 | discard | Revenue growth acceleration: difference between recent and older YoY growth. |
| none | none | L1 | discard | Residual win rate: fraction of positive residual-return days 120d. |
| none | none | L1 | discard | Max-volume day return: return on highest-volume day in 60d. |
| none | none | L2 | discard | Volume autocorrelation: persistence of daily volume 120d. |
| none | none | L2 | discard | Intraday return share: fraction of return from intraday moves. |
| none | none | L1 | discard | Volume-weighted mean return: weight daily returns by volume 120d. |
| none | none | L1 | discard | Multi-scale residual momentum: avg idiosyncratic return 60/90/120d. |
| none | none | L1 | discard | Hurst exponent: tendency to trend vs mean-revert over 240d. |
| none | none | L2 | discard | Daily winner frequency: fraction of days in top tercile 120d. |
| none | none | L1 | discard | Intraday absorption score: recovery from overnight gaps 120d. |
| none | none | L1 | discard | Chaikin Money Flow 60d: volume-weighted close location value. |
| none | none | L1 | discard | Residual momentum t-stat: idiosyncratic return / residual vol. |
| weak | weak | L2 | discard | Residual momentum: idiosyncratic return after removing market beta. |
| none | none | L1 | discard | Residual momentum: idiosyncratic return after removing market beta. |
| weak | weak | L2 | discard | Residual momentum: idiosyncratic return after removing market beta. |
| none | none | L2 | discard | Quiet-day momentum: average return on below-median volume days. |
| none | none | L2 | discard | Negative volume concentration (Herfindahl): even volume spread. |
| none | none | L2 | discard | Volume-price rank divergence: high volume rank minus price rank. |
| none | none | L1 | discard | VWAP distance: close relative to 60-day volume-weighted avg price. |
| none | none | L1 | discard | Volume-confirmed momentum: rank(120d ret) × rank(volume increase). |
| none | none | L1 | discard | Persistent momentum: min of 60d and 120d returns, skip 5d. |
| weak | weak | L2 | discard | Risk-adjusted alpha: residual return after cross-sectional vol control. |
| none | none | L1 | discard | Recency of 120d high: negative days since last 120-day high price. |
| weak | weak | L2 | discard | Kelly ratio: mean(return) / variance(return) 120d skip 5d. |
| none | none | L1 | discard | Upside capture: sum(log(high/open)) minus sum(log(open/low)) 120d. |
| weak | weak | L2 | discard | Regime-adaptive momentum/reversal: trend in upmarket, contrarian in down. |
| none | none | L2 | discard | Volume-price divergence: sign(volume_change) × (-price_change) 60d. |
| none | none | L1 | discard | Overnight return autocorrelation: persistence of overnight info 120d. |
| weak | weak | L2 | discard | Trend t-statistic: significance of linear price trend over 120d. |
| none | none | L2 | discard | Trend acceleration: quadratic coefficient of log-price on time 120d. |
| weak | weak | L2 | discard | Multi-scale trend quality: avg Spearman(time, price) at 60/120/240d. |
| none | none | L1 | discard | Sortino ratio: mean return / downside deviation 120d skip 5d. |
| none | none | L1 | discard | Intraday bullishness: fraction of close > open days over 120d. |
| none | none | L1 | discard | Medium-term reversal: negative 60d return skip 5d, buy losers. |
| none | none | L2 | discard | Volume evenness: negative HHI of daily volume shares over 120d. |
| weak | weak | L2 | discard | Weekly Sharpe ratio: mean/std of 5-day non-overlapping returns 120d. |
| weak | weak | L2 | discard | In-sample Sharpe ratio: mean/std of daily returns 120d skip 5d. |
| weak | weak | L2 | discard | Time above trend: fraction of 120 days close is above its own MA120. |
| none | none | L2 | discard | Volume autocorrelation: lag-1 autocorrelation of daily volume 120d. |
| weak | weak | L2 | discard | Trend-quality low-vol: rank(Spearman) × rank(neg vol) 120d. |
| none | none | L2 | discard | Trend quality composite: rank(price-time Spearman) + rank(neg vol) 120d. |
| weak | weak | L2 | discard | Price-time rank correlation: Spearman corr of time vs price 120d. |
| none | none | L2 | discard | Short momentum × long low-vol: rank(40d ret) × rank(neg 240d vol). |
| none | none | L1 | discard | Volume-weighted return: sum(ret*vol)/sum(vol) over 120d skip 5d. |
| none | none | L1 | discard | Risk-adjusted momentum: Sharpe ratio of daily returns 240d skip 20d. |
| weak | weak | L2 | discard | Momentum inflection: recent 20d return minus prior 100d return. |
| weak | weak | L2 | discard | Quality momentum: rank(240d return skip 20d) × rank(neg 240d vol). |
| weak | weak | L2 | discard | Momentum-vol interaction: rank(return_120d) × rank(neg_vol_120d). |
| none | none | L1 | discard | Idiosyncratic momentum: 120d return minus market return, skip 5d. |
| none | none | L2 | discard | Overnight return Sharpe ratio: mean/std of overnight returns 120d. |
| none | none | L2 | discard | Multi-scale low vol: negative median of volatility at 60/120/240d. |
| none | none | L2 | discard | Lower-to-upper shadow ratio: buying support vs selling pressure 120d. |
| none | none | L2 | discard | Ranked low volatility: cross-sectional rank of negative 120d vol. |
| none | none | L2 | discard | Negative CVaR 5%: expected shortfall tail risk avoidance 240d. |
| none | none | L1 | discard | Institutional flow t-statistic: consistency of total net buying 120d. |
| none | none | L1 | discard | Foreign-confirmed overnight momentum: overnight return × sign(foreign_net). |
| none | none | L1 | discard | PER decline rate: negative 60d change in P/E ratio signals cheapening. |
| none | none | L1 | discard | Foreign buying breadth: fraction of days with positive foreign_net 120d. |
| none | none | L1 | discard | Gap persistence rate: fraction of overnight gaps not reversed intraday. |
| none | none | L2 | discard | Close-to-high ratio: avg(close/high) over 120 days. |
| none | none | L1 | discard | Long-term reversal: negative 240d return skip 20d (DeBondt-Thaler). |
| none | none | L2 | discard | Short-term momentum: 20-day return captures continuation of recent trends. |
| none | none | L1 | discard | Volume-return asymmetry: avg volume on up days / avg volume on down days. |
| none | none | L1 | discard | Negative Parkinson-to-close vol ratio: low range noise = efficient pricing. |
| none | none | L1 | discard | Variance ratio (k=5): weekly vs daily return variance over 120 days. |
| none | none | L2 | discard | Turnover stability: negative CV of daily turnover over 120 days. |
| none | none | L1 | discard | Beta asymmetry: upside beta minus downside beta over 120 days. |
| none | none | L2 | discard | Negative max drawdown 120d: stocks with shallower drawdowns outperform. |
| none | none | L2 | discard | Overnight-intraday vol ratio: overnight std / intraday std 120d. |
| weak | weak | L2 | discard | Daily Sharpe ratio: mean/std of daily returns over 120 days. |
| none | none | L2 | discard | Dual efficiency: intraday range efficiency + price path efficiency. |
| none | none | L1 | discard | Dual efficiency: intraday range efficiency + price path efficiency 120d. |
| none | none | L2 | discard | Signed intraday efficiency: avg (close-open)/(high-low) over 120d. |
| weak | weak | L2 | discard | Intraday directional efficiency: |close-open|/(high-low) avg 120d. |
| weak | weak | L2 | discard | Trend reversal: negative Spearman price-time correlation 120d. |
| none | none | L1 | discard | Confirmed trend: Spearman trend strength filtered by foreign flow sign. |
| none | none | L2 | discard | Close-volume alignment: corr of daily closing position and volume 120d. |
| weak | weak | L2 | discard | Trend strength: Spearman price-time rank correlation over 240d. |
| weak | weak | L2 | discard | Trend strength: Spearman price-time correlation 120d skip 20d. |
| weak | weak | L2 | discard | Trend strength: Spearman rank correlation of price with time 120d. |
| none | none | L2 | discard | Gap continuation: fraction of overnight gaps that persist to close 120d. |
| none | none | L1 | discard | Positive coskewness: stocks that rise when market volatility spikes. |
| none | none | L1 | discard | Median daily return: robust central tendency of daily returns 120d. |
| none | none | L2 | discard | Closing strength: average (close-low)/(high-low) over 120 days. |
| none | none | L1 | discard | Price path efficiency: net return / sum |daily returns| 240d skip 20d. |
| none | none | L1 | discard | Negative return-flow correlation: contrarian foreign buying predicts reversal. |
| none | none | L2 | discard | Up-volume fraction: ratio of volume on up-days to total volume 120d. |
| weak | weak | L2 | discard | Relative mean reversion: buy stocks with declining rank (20d vs 120d). |
| none | none | L1 | discard | Rank acceleration: cross-sectional return rank 40d minus rank 200d. |
| weak | weak | L2 | discard | Rank improvement: cross-sectional return rank change 20d vs 120d. |
| none | none | L1 | discard | Gain-loss ratio: sum of positive returns / absolute negative returns 240d. |
| weak | weak | L2 | discard | Gain-loss ratio: sum of positive returns / sum of negative returns 120d. |
| none | none | L1 | discard | Trend-volume interaction: MA distance times volume surge. |
| none | none | L1 | discard | Low turnover premium: negative average daily turnover rate 120d. |
| weak | weak | L2 | discard | Composite: low vol rank + overnight return rank + trend efficiency rank. |
| none | none | L2 | discard | Low return kurtosis: negative excess kurtosis of daily returns 240d. |
| none | none | L2 | discard | Idiosyncratic overnight return: beta-adjusted cumulative overnight 120d. |
| none | none | L2 | discard | Idiosyncratic overnight return: beta-adjusted cumulative overnight 120d. |
| none | none | L2 | discard | Return-volume correlation: Spearman rank corr of daily returns and |
| none | none | L2 | discard | Volume trend: ratio of recent 20d avg volume to prior 60d avg volume. |
| none | none | L1 | discard | Efficient momentum: 120d return weighted by path directional coherence. |
| none | none | L1 | discard | Small size premium: negative log average dollar volume over 60d. |
| weak | weak | L2 | discard | Smoothed price efficiency: avg of 3 overlapping 60d efficiency scores. |
| none | none | L1 | discard | Price path efficiency: net return / total absolute path, 60d window. |
| weak | weak | L2 | discard | Price efficiency: net return over sum of absolute daily returns 120d. |
| none | none | L2 | discard | Variance ratio: weekly vs daily return variance ratio over 120d. |
| none | none | L1 | discard | Foreign flow trend: slope of cumulative foreign net buying 60d. |
| none | none | L2 | discard | Momentum acceleration: recent 60d return minus prior 60d return. |
| none | none | L2 | discard | Low weekly volatility: negative std of weekly returns over 52 weeks. |
| none | none | L1 | discard | Volatility-adjusted mean reversion: negative 40d return / volatility. |
| none | none | L1 | discard | PER percentile reversion: current PER rank within own 2-year history. |
| none | none | L1 | discard | Foreign-trust flow divergence: foreign buying minus trust buying 40d. |
| none | none | L1 | discard | Volume-weighted return sign: sum of sign(return)*volume over 60d. |
| none | none | L2 | discard | Return autocorrelation: serial correlation of daily returns over 120 days. |
| none | none | L1 | discard | Residual momentum: idiosyncratic return 240d skip 20d. |
| weak | weak | L2 | discard | Residual momentum: idiosyncratic return after removing market. |
| none | none | L2 | discard | Close above typical price: late-day accumulation signal. |
| weak | weak | L2 | discard | Gradual momentum + dealer flow: two orthogonal signals combined. |
| none | none | L1 | discard | Daily win rate: excess fraction of up days over 120 trading days. |
| none | none | L1 | discard | New high frequency: count of 20-day highs in past 60 days. |
| none | none | L1 | discard | Long frog-in-pan: 240-day gradual trend continuity signal. |
| weak | weak | L2 | discard | Frog-in-pan with skip: gradual movers skip recent 20 days. |
| none | none | L1 | discard | Regime-conditional momentum: bull=momentum, bear=reversal. |
| none | none | L2 | discard | Low intraday range: narrow daily high-low spread over 120d. |
| none | none | L2 | discard | Min daily return avoidance: avoid recent extreme drawdowns. |
| none | none | L1 | discard | Long-term reversal: negative of 12-month return (contrarian). |
| none | none | L2 | discard | Negative price-volume correlation: low corr predicts returns. |
| none | none | L1 | discard | Trust fund buying intensity: normalized domestic fund flow 60d. |
| none | none | L2 | discard | Return acceleration: recent momentum minus prior momentum. |
| none | none | L1 | discard | 40-day return reversal: intermediate-term mean reversion. |
| none | none | L2 | discard | Volatility decrease: declining realized vol signals risk resolution. |
| none | none | L1 | discard | High-attention day returns: price moves on above-average volume. |
| none | none | L1 | discard | Time-series momentum z-score: current 6m return vs own history. |
| none | none | L1 | discard | Intraday vs overnight return divergence: institutional vs retail. |
| none | none | L2 | discard | Low weekly volatility: negative of 52-week vol at weekly freq. |
| none | none | L2 | discard | Intraday minus overnight return spread over 60 days. |
| none | none | L2 | discard | Cumulative intraday returns over 120 days for stability. |
| none | none | L2 | discard | Cumulative intraday returns: close-to-open move over 60 days. |
| weak | weak | L2 | discard | Normalized dealer flow intensity over 120 trading days. |
| weak | weak | L2 | discard | Normalized dealer net buying: hedging flow intensity over 60d. |
| none | none | L2 | discard | Dealer net buying trend: option-hedging flow as leading indicator. |
| weak | weak | L2 | discard | Weekly momentum: 26-week return skip 4 weeks at weekly freq. |
| none | none | L1 | discard | Variance ratio: price trending vs mean-reverting tendency. |
| none | none | L2 | discard | Low-beta anomaly with 240-day estimation for stability. |
| none | none | L2 | discard | Low-beta anomaly: stocks with low market beta earn excess returns. |
| none | none | L1 | discard | Frog-in-the-Pan 60d: gradual movers with persistent direction. |
| none | none | L1 | discard | Simple 6-month price momentum (raw 120-day return). |
| none | none | L1 | discard | Trend quality: R-squared of log-price regression times slope. |
| none | none | L1 | discard | Magnitude-weighted frog-in-pan: large gradual moves persist. |
| weak | weak | L2 | discard | Frog-in-the-Pan: gradual winners have under-noticed momentum. |
| none | none | L2 | discard | Low realized volatility premium over 240 trading days. |
| none | none | L1 | discard | Overnight accumulation in low-vol stocks. |
| none | none | L2 | discard | Anti-lottery: negative of maximum daily return over 60 days. |
| none | none | L1 | discard | Accumulation/Distribution trend: volume-weighted close position. |
| none | none | L1 | discard | Foreign conviction buying: net foreign buying on down-price days. |
| none | none | L1 | discard | Money flow ratio: up-volume vs down-volume over 60 days. |
| none | none | L2 | discard | Closing strength: close position within daily high-low range. |
| none | none | L2 | discard | EMA-smoothed cumulative overnight returns over 120 days. |
| none | none | L2 | discard | Cumulative overnight returns over 60 days as institutional signal. |
| none | none | L1 | discard | Multi-scale momentum: average of 1m, 3m, 6m returns skip 5d. |
| none | none | L1 | discard | Intraday range compression predicts future breakout direction. |
| none | none | L1 | discard | Volume-weighted price trend: rank stocks by recent price change |
| none | none | L2 | discard | Anti-lottery: avoid stocks with extreme positive daily returns. |
| none | none | L1 | discard | Intraday buying pressure: close position within high-low range. |
| none | none | L2 | discard | Low downside risk: negative semideviation over 120 days. |
| none | none | L2 | discard | Cumulative overnight returns: informed after-hours activity. |
| none | none | L1 | discard | Institutional consensus: foreign + trust both net buying. |
| none | none | L1 | discard | Total institutional net buying 60d: combined smart money flow. |
| none | none | L1 | discard | Price relative to 200-day MA: trend strength indicator. |
| none | none | L1 | discard | Return consistency: fraction of positive return days over 60 days. |
| none | none | L1 | discard | 3-month momentum skip 5 days: intermediate-term trend following. |
| none | none | L1 | discard | OBV slope: on-balance volume trend reveals accumulation. |
| none | none | L2 | discard | Quality momentum: 5-month return divided by realized volatility. |
| none | none | L1 | discard | EMA trend strength: 50/200 day exponential MA ratio. |
| none | none | L2 | discard | Quality momentum: rising price with low volatility. |
| none | none | L2 | discard | Relative strength: small drawdown from 60-day peak. |
| none | none | L2 | discard | 20-day return reversal: short-term overreaction mean-reversion. |
| none | none | L1 | discard | Smoothed 6-month momentum: MA-endpoints reduce noise. |
| none | none | L1 | discard | Amihud illiquidity ratio: illiquid stocks earn risk premium. |
| none | none | L1 | discard | Amihud illiquidity ratio: illiquid stocks earn risk premium. |
| none | none | L1 | discard | Investment trust cumulative net buying: smart money flow. |
| none | none | L1 | discard | Trust (投信) buying acceleration: smart domestic money flow trend. |
| none | none | L2 | discard | 12-month momentum skip recent month (classic Jegadeesh-Titman). |
| none | none | L1 | discard | 12-month momentum skip recent month (classic Jegadeesh-Titman). |
| none | none | L1 | discard | Margin usage contrarian: high retail leverage predicts poor returns. |
| none | none | L1 | discard | Margin usage decline as contrarian buy signal. |
| none | none | L1 | discard | Low PBR value factor using trailing PBR history. |
| none | none | L1 | discard | Low PBR value factor using trailing PBR history. |
| none | none | L1 | discard | Low PER value factor using trailing PER history. |
| weak | weak | L2 | discard | 6-month price momentum skipping recent month (Jegadeesh-Titman). |
| weak | weak | L2 | discard | 6-month price momentum skipping recent month (Jegadeesh-Titman). |
| none | none | L1 | discard | Revenue YoY growth momentum: high growth predicts returns. |
| none | none | L1 | discard | Foreign institutional cumulative net buying scaled by volume. |
| none | none | L1 | discard | Foreign institutional cumulative net buying scaled by volume. |
| none | none | L1 | discard | Turnover surge with positive price drift: conviction-backed momentum. |
| none | none | L1 | discard | Turnover rate change: rising volume relative to price signals conviction. |
| none | none | L1 | discard | Shrinking daily range ratio: volatility compression precedes breakouts. |
| none | none | L1 | discard | Smoothed 90-day return: captures medium-term price trend. |
| none | none | L1 | discard | Baseline: simple 20-day return. |

## Alerts

- `[2026-03-31 21:00:31] STALE: No new results for 57 minutes`
- `[2026-03-31 21:01:37] STALE: No new results for 58 minutes`
- `[2026-03-31 21:02:45] STALE: No new results for 59 minutes`
- `[2026-03-31 21:03:52] STALE: No new results for 60 minutes`
- `[2026-03-31 21:04:59] STALE: No new results for 62 minutes`
- `[2026-03-31 21:06:06] STALE: No new results for 63 minutes`
- `[2026-03-31 21:07:13] STALE: No new results for 64 minutes`
- `[2026-03-31 21:08:20] STALE: No new results for 65 minutes`
- `[2026-03-31 21:09:27] STALE: No new results for 66 minutes`
- `[2026-03-31 21:10:34] STALE: No new results for 67 minutes`

---
*Auto-generated by `scripts/autoresearch/status.ps1`*
