package com.quant.trading.ui.screens.trading.paper

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
fun PaperTradingTab(viewModel: PaperTradingViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Paper Trading Status
        state.paperStatus?.let { ps ->
            QuantCard {
                Column(Modifier.padding(16.dp)) {
                    Text(stringResource(R.string.paper_status), style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard(label = "NAV", value = Format.currency(ps.portfolioNav), modifier = Modifier.weight(1f))
                        MetricCard(label = "Open Orders", value = ps.openOrders.toString(), modifier = Modifier.weight(1f))
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        StatusBadge(if (ps.active) "Active" else "Inactive")
                        StatusBadge(if (ps.brokerConnected) "Connected" else "Disconnected")
                    }
                }
            }
        }

        // Market Hours
        state.marketHours?.let { mh ->
            QuantCard {
                Column(Modifier.padding(16.dp)) {
                    Text(stringResource(R.string.paper_market_hours), style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(8.dp))
                    Text("Session: ${mh.session}", style = MaterialTheme.typography.bodyMedium)
                    Text("Tradable: ${if (mh.isTradable) "Yes" else "No"}", style = MaterialTheme.typography.bodySmall)
                    Text("Next Open: ${mh.nextOpen}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        // Reconcile
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = viewModel::reconcile, modifier = Modifier.weight(1f)) {
                Text(stringResource(R.string.paper_reconcile))
            }
            OutlinedButton(onClick = viewModel::autoCorrect, modifier = Modifier.weight(1f)) {
                Text(stringResource(R.string.paper_auto_correct))
            }
        }

        state.reconcileResult?.let { r ->
            QuantCard {
                Column(Modifier.padding(16.dp)) {
                    Text("Reconcile: ${r.summary}", style = MaterialTheme.typography.bodySmall)
                    Text("Matched: ${r.matched} · Mismatched: ${r.mismatched}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        // Queued orders
        state.queuedOrders?.let { q ->
            QuantCard {
                Column(Modifier.padding(16.dp)) {
                    Text("${stringResource(R.string.paper_queued)} (${q.count})", style = MaterialTheme.typography.titleSmall)
                    q.orders.forEach { o ->
                        Text("${o.symbol} · ${Format.time(o.timestamp)}", style = MaterialTheme.typography.bodySmall)
                    }
                    if (q.orders.isEmpty()) EmptyState()
                }
            }
        }

        if (state.loading) PageSkeleton()

        state.error?.let { ErrorAlert(it, onRetry = viewModel::load) }
    }
}
