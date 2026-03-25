package com.quant.trading.ui.screens.strategies

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.quant.trading.R
import com.quant.trading.ui.components.*
import com.quant.trading.util.Format

@Composable
fun StrategiesScreen(viewModel: StrategiesViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    if (state.loading && state.strategies.isEmpty()) { PageSkeleton(); return }
    state.error?.let { ErrorAlert(it, onRetry = viewModel::load); return }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        contentPadding = PaddingValues(vertical = 16.dp),
    ) {
        item {
            Text(stringResource(R.string.nav_strategies), style = MaterialTheme.typography.headlineSmall)
        }

        if (state.strategies.isEmpty()) {
            item { EmptyState() }
        } else {
            items(state.strategies) { s ->
                QuantCard {
                    Row(
                        modifier = Modifier.padding(16.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                text = s.name,
                                style = MaterialTheme.typography.titleSmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Spacer(Modifier.height(4.dp))
                            Row(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                StatusBadge(s.status)
                                PnlText(value = s.pnl, formatted = Format.currency(s.pnl), style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        if (s.status == "running") {
                            OutlinedButton(onClick = { viewModel.stop(s.name) }) {
                                Text(stringResource(R.string.strategy_stop))
                            }
                        } else {
                            Button(onClick = { viewModel.start(s.name) }) {
                                Text(stringResource(R.string.strategy_start))
                            }
                        }
                    }
                }
            }
        }
    }
}
