package com.quant.trading.ui.screens.guide

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.quant.trading.R
import com.quant.trading.ui.components.QuantCard

data class GuideChapter(val title: String, val content: String)

@Composable
fun GuideScreen() {
    val chapters = listOf(
        GuideChapter(stringResource(R.string.guide_overview), "This platform is a multi-asset portfolio research and optimization system. It supports TW stocks, US stocks, ETFs, TW futures, and US futures. Use the Dashboard to monitor positions, Trading to manage portfolios and orders, Research for backtesting and alpha analysis, and Risk for risk management."),
        GuideChapter(stringResource(R.string.guide_backtest), "Navigate to Research → Backtest tab. Enter a strategy name (e.g., momentum, ma_crossover, mean_reversion), add symbols to the universe, set the date range, and click Run. Results show total return, Sharpe ratio, max drawdown, and trade statistics."),
        GuideChapter(stringResource(R.string.guide_alpha), "Navigate to Research → Alpha Research tab. The alpha pipeline computes factor exposures (momentum, volatility, mean reversion, etc.), calculates IC (Information Coefficient), and generates quantile return analysis. Use this for factor-based stock selection research."),
        GuideChapter(stringResource(R.string.guide_allocation), "Navigate to Research → Allocation tab. Tactical allocation combines strategic weights with macro signals (growth, inflation, rates, credit), cross-asset momentum, and regime detection to produce optimal asset class weights."),
        GuideChapter(stringResource(R.string.guide_risk), "Navigate to Risk. View and toggle risk rules, monitor alerts, and use the Kill Switch (risk_manager role required) to emergency-stop all strategies and cancel pending orders."),
        GuideChapter(stringResource(R.string.guide_paper_trading), "Navigate to Trading → Paper Trading tab. View paper trading status, market hours, reconcile positions between system and broker, and monitor queued orders. This simulates real trading without actual execution."),
        GuideChapter(stringResource(R.string.guide_faq), "Q: What data sources are supported?\nA: Yahoo Finance (default) and FinMind for TW stocks.\n\nQ: What is the default commission rate?\nA: 0.1425% (Taiwan stock market default).\n\nQ: How do I add a new strategy?\nA: Create a Python file in strategies/, subclass Strategy, implement name() and on_bar()."),
    )

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Text(stringResource(R.string.guide_title), style = MaterialTheme.typography.headlineSmall)
            Spacer(Modifier.height(8.dp))
        }

        items(chapters) { chapter ->
            var expanded by remember { mutableStateOf(false) }
            QuantCard {
                Column(
                    modifier = Modifier
                        .clickable { expanded = !expanded }
                        .padding(16.dp),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(chapter.title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                        Icon(
                            if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = null,
                        )
                    }
                    AnimatedVisibility(visible = expanded) {
                        Text(
                            chapter.content,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                    }
                }
            }
        }
    }
}
