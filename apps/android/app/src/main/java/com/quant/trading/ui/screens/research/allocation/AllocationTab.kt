package com.quant.trading.ui.screens.research.allocation

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
fun AllocationTab(viewModel: AllocationViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Button(onClick = viewModel::compute, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) {
            if (state.loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
            else Text(stringResource(R.string.allocation_compute))
        }

        state.error?.let { ErrorAlert(it) }

        state.result?.let { r ->
            // Regime
            QuantCard {
                Column(Modifier.padding(16.dp)) {
                    Text("${stringResource(R.string.allocation_regime)}: ${r.regime}", style = MaterialTheme.typography.titleSmall)
                }
            }

            // Weights
            QuantCard {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Tactical Weights", style = MaterialTheme.typography.titleSmall)
                    r.weights.forEach { w ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(w.assetClass, style = MaterialTheme.typography.bodyMedium)
                            Text(Format.pct(w.tacticalWeight), style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }

            // Macro signals
            QuantCard {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(stringResource(R.string.allocation_macro), style = MaterialTheme.typography.titleSmall)
                    r.macroSignals.forEach { s ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(s.name, style = MaterialTheme.typography.bodyMedium)
                            Text("%.2f".format(s.value), style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}
