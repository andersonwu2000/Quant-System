package com.quant.trading.ui.screens.risk

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
fun RiskScreen(viewModel: RiskViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    var showKillSwitch by remember { mutableStateOf(false) }

    if (state.loading && state.rules.isEmpty()) { PageSkeleton(); return }
    state.error?.let { ErrorAlert(it, onRetry = viewModel::load); return }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        contentPadding = PaddingValues(vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Text(stringResource(R.string.nav_risk), style = MaterialTheme.typography.headlineSmall)
        }

        // Kill Switch (risk_manager+)
        if (state.role == "risk_manager" || state.role == "admin") {
            item {
                Button(
                    onClick = { showKillSwitch = true },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.risk_kill_switch))
                }
            }
        }

        // Rules
        item { Text(stringResource(R.string.risk_rules), style = MaterialTheme.typography.titleMedium) }
        items(state.rules) { rule ->
            QuantCard {
                Row(
                    modifier = Modifier.padding(16.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(rule.name, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Switch(
                        checked = rule.enabled,
                        onCheckedChange = { viewModel.toggleRule(rule.name, it) },
                        enabled = state.role == "risk_manager" || state.role == "admin",
                    )
                }
            }
        }

        // Alerts
        item { Text(stringResource(R.string.risk_alerts), style = MaterialTheme.typography.titleMedium) }
        if (state.alerts.isEmpty()) {
            item { EmptyState() }
        } else {
            items(state.alerts) { alert ->
                QuantCard {
                    Column(Modifier.padding(16.dp)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            StatusBadge(alert.severity)
                            Text(alert.ruleName, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        Text(alert.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(Format.date(alert.timestamp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }

    if (showKillSwitch) {
        ConfirmDialog(
            title = stringResource(R.string.risk_kill_switch),
            message = stringResource(R.string.risk_kill_confirm),
            isDangerous = true,
            onConfirm = viewModel::killSwitch,
            onDismiss = { showKillSwitch = false },
        )
    }
}
