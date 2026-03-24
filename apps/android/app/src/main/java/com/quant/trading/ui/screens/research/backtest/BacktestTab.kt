package com.quant.trading.ui.screens.research.backtest

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
fun BacktestTab(viewModel: BacktestViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Input form
        QuantCard {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = state.strategy, onValueChange = viewModel::updateStrategy, label = { Text(stringResource(R.string.backtest_strategy)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = state.universe, onValueChange = viewModel::updateUniverse, label = { Text(stringResource(R.string.backtest_universe)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = state.startDate, onValueChange = viewModel::updateStartDate, label = { Text(stringResource(R.string.backtest_start_date)) }, singleLine = true, modifier = Modifier.weight(1f))
                    OutlinedTextField(value = state.endDate, onValueChange = viewModel::updateEndDate, label = { Text(stringResource(R.string.backtest_end_date)) }, singleLine = true, modifier = Modifier.weight(1f))
                }
                Button(
                    onClick = viewModel::run,
                    enabled = !state.running,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (state.running) {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                        Spacer(Modifier.width(8.dp))
                        Text("${(state.progress * 100).toInt()}%")
                    } else {
                        Text(stringResource(R.string.backtest_run))
                    }
                }
            }
        }

        // Progress
        if (state.running) {
            LinearProgressIndicator(progress = { state.progress }, modifier = Modifier.fillMaxWidth())
        }

        // Error
        state.error?.let { ErrorAlert(it) }

        // Result
        state.result?.let { r ->
            QuantCard {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("${r.strategyName} Result", style = MaterialTheme.typography.titleMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard(label = stringResource(R.string.backtest_total_return), value = Format.pct(r.totalReturn), modifier = Modifier.weight(1f))
                        MetricCard(label = stringResource(R.string.backtest_annual_return), value = Format.pct(r.annualReturn), modifier = Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard(label = stringResource(R.string.backtest_sharpe), value = "%.2f".format(r.sharpe), modifier = Modifier.weight(1f))
                        MetricCard(label = stringResource(R.string.backtest_max_dd), value = Format.pct(r.maxDrawdown), modifier = Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard(label = stringResource(R.string.backtest_trades), value = r.totalTrades.toString(), modifier = Modifier.weight(1f))
                        MetricCard(label = stringResource(R.string.backtest_win_rate), value = Format.pct(r.winRate), modifier = Modifier.weight(1f))
                    }
                }
            }
        }
    }
}
