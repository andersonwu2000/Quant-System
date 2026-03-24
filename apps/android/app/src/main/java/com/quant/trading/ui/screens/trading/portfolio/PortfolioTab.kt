package com.quant.trading.ui.screens.trading.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.quant.trading.R
import com.quant.trading.ui.components.*
import com.quant.trading.util.Format

@Composable
fun PortfolioTab(viewModel: PortfolioViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    var showCreate by remember { mutableStateOf(false) }
    var deleteTarget by remember { mutableStateOf<String?>(null) }

    if (state.loading && state.portfolios.isEmpty()) {
        PageSkeleton()
        return
    }

    state.error?.let { err ->
        ErrorAlert(message = err, onRetry = viewModel::load)
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(stringResource(R.string.portfolio_saved), style = MaterialTheme.typography.titleMedium)
                IconButton(onClick = { showCreate = true }) {
                    Icon(Icons.Default.Add, contentDescription = stringResource(R.string.portfolio_create))
                }
            }
        }

        if (state.portfolios.isEmpty()) {
            item { EmptyState() }
        } else {
            items(state.portfolios) { p ->
                QuantCard {
                    Row(
                        modifier = Modifier.padding(12.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(p.name, style = MaterialTheme.typography.titleSmall)
                            Text(
                                "${p.strategyName} · ${p.positionCount} positions",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                "Cash: ${Format.currency(p.cash)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        IconButton(onClick = { deleteTarget = p.id }) {
                            Icon(Icons.Default.Delete, contentDescription = stringResource(R.string.delete), tint = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
        }
    }

    // Create dialog
    if (showCreate) {
        var name by remember { mutableStateOf("") }
        var cash by remember { mutableStateOf("1000000") }

        AlertDialog(
            onDismissRequest = { showCreate = false },
            title = { Text(stringResource(R.string.portfolio_create)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text(stringResource(R.string.portfolio_name)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = cash, onValueChange = { cash = it }, label = { Text(stringResource(R.string.portfolio_initial_cash)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
            },
            confirmButton = {
                Button(onClick = {
                    viewModel.create(name, cash.toDoubleOrNull() ?: 1_000_000.0)
                    showCreate = false
                }) { Text(stringResource(R.string.save)) }
            },
            dismissButton = { TextButton(onClick = { showCreate = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }

    // Delete confirmation
    deleteTarget?.let { id ->
        ConfirmDialog(
            title = stringResource(R.string.delete),
            message = stringResource(R.string.portfolio_delete_confirm),
            isDangerous = true,
            onConfirm = { viewModel.delete(id) },
            onDismiss = { deleteTarget = null },
        )
    }
}
