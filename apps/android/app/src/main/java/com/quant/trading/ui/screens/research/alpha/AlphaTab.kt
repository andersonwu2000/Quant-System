package com.quant.trading.ui.screens.research.alpha

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.quant.trading.R
import com.quant.trading.ui.components.*

@Composable
fun AlphaTab(viewModel: AlphaViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        contentPadding = PaddingValues(vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // Input
        item {
            QuantCard {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = state.universe, onValueChange = viewModel::updateUniverse, label = { Text(stringResource(R.string.backtest_universe)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(value = state.startDate, onValueChange = viewModel::updateStartDate, label = { Text(stringResource(R.string.backtest_start_date)) }, singleLine = true, modifier = Modifier.weight(1f))
                        OutlinedTextField(value = state.endDate, onValueChange = viewModel::updateEndDate, label = { Text(stringResource(R.string.backtest_end_date)) }, singleLine = true, modifier = Modifier.weight(1f))
                    }
                    Button(onClick = viewModel::run, enabled = !state.running, modifier = Modifier.fillMaxWidth()) {
                        if (state.running) {
                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                        } else {
                            Text(stringResource(R.string.alpha_run))
                        }
                    }
                }
            }
        }

        state.error?.let { item { ErrorAlert(it) } }

        // Factor results
        state.report?.factors?.let { factors ->
            items(factors) { f ->
                QuantCard {
                    Column(Modifier.padding(16.dp)) {
                        Text(f.name, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Spacer(Modifier.height(4.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            MetricCard(label = stringResource(R.string.alpha_ic), value = "%.4f".format(f.ic.icMean), modifier = Modifier.weight(1f))
                            MetricCard(label = stringResource(R.string.alpha_icir), value = "%.2f".format(f.ic.icir), modifier = Modifier.weight(1f))
                            MetricCard(label = stringResource(R.string.alpha_sharpe), value = "%.2f".format(f.longShortSharpe), modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}
