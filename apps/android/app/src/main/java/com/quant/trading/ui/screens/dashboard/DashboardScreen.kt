package com.quant.trading.ui.screens.dashboard

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.quant.trading.R
import com.quant.trading.ui.components.*
import com.quant.trading.util.Format

@Composable
fun DashboardScreen(viewModel: DashboardViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    if (state.loading && state.portfolio == null) {
        PageSkeleton()
        return
    }

    state.error?.let { err ->
        ErrorAlert(message = err, onRetry = viewModel::loadPortfolio)
        return
    }

    val p = state.portfolio ?: return

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Connection banner
        item {
            ConnectionBanner(connected = state.wsConnected)
        }

        // Title
        item {
            Text(stringResource(R.string.nav_dashboard), style = MaterialTheme.typography.headlineSmall)
        }

        // Metric cards row 1
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MetricCard(
                    label = stringResource(R.string.dashboard_nav),
                    value = Format.currency(p.nav),
                    modifier = Modifier.weight(1f),
                )
                MetricCard(
                    label = stringResource(R.string.dashboard_cash),
                    value = Format.currency(p.cash),
                    modifier = Modifier.weight(1f),
                )
            }
        }

        // Metric cards row 2
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MetricCard(
                    label = stringResource(R.string.dashboard_daily_pnl),
                    value = Format.currency(p.dailyPnl),
                    sub = Format.pct(p.dailyPnlPct),
                    valueColor = if (p.dailyPnl >= 0) com.quant.trading.ui.theme.PnlPositive else com.quant.trading.ui.theme.PnlNegative,
                    modifier = Modifier.weight(1f),
                )
                MetricCard(
                    label = stringResource(R.string.dashboard_positions),
                    value = p.positionsCount.toString(),
                    modifier = Modifier.weight(1f),
                )
            }
        }

        // Positions table
        item {
            Text(stringResource(R.string.dashboard_positions), style = MaterialTheme.typography.titleMedium)
        }

        if (p.positions.isEmpty()) {
            item { EmptyState() }
        } else {
            items(p.positions) { pos ->
                QuantCard {
                    Row(
                        modifier = Modifier.padding(12.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column {
                            Text(pos.symbol, style = MaterialTheme.typography.titleSmall)
                            Text(
                                "Qty: ${pos.quantity.toInt()} · Avg: ${Format.price(pos.avgCost)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Column(horizontalAlignment = androidx.compose.ui.Alignment.End) {
                            Text(Format.currency(pos.marketValue), style = MaterialTheme.typography.titleSmall)
                            PnlText(
                                value = pos.unrealizedPnl,
                                formatted = Format.currency(pos.unrealizedPnl),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }
        }
    }
}
