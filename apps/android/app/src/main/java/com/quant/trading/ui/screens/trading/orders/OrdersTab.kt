package com.quant.trading.ui.screens.trading.orders

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
import com.quant.trading.util.Format

@Composable
fun OrdersTab(viewModel: OrdersViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    var showOrderForm by remember { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        contentPadding = PaddingValues(vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // Filter chips
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(null to R.string.order_filter_all, "open" to R.string.order_filter_open, "filled" to R.string.order_filter_filled).forEach { (filter, resId) ->
                    FilterChip(
                        selected = state.filter == filter,
                        onClick = { viewModel.setFilter(filter) },
                        label = { Text(stringResource(resId)) },
                    )
                }
            }
        }

        // New order button
        item {
            Button(onClick = { showOrderForm = true }, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.order_submit))
            }
        }

        if (state.loading) {
            item { PageSkeleton() }
        } else if (state.orders.isEmpty()) {
            item { EmptyState() }
        } else {
            items(state.orders) { order ->
                QuantCard {
                    Row(
                        modifier = Modifier.padding(16.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column {
                            Text("${order.side} ${order.symbol}", style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(
                                "Qty: ${order.quantity} · ${Format.date(order.createdAt)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Column(horizontalAlignment = androidx.compose.ui.Alignment.End) {
                            StatusBadge(order.status)
                            if (order.filledQty > 0) {
                                Text(
                                    "Filled: ${order.filledQty} @ ${Format.price(order.filledAvgPrice)}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    // Order form dialog
    if (showOrderForm) {
        var symbol by remember { mutableStateOf("") }
        var side by remember { mutableStateOf("BUY") }
        var qty by remember { mutableStateOf("") }
        var price by remember { mutableStateOf("") }

        AlertDialog(
            onDismissRequest = { showOrderForm = false },
            title = { Text(stringResource(R.string.order_submit)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = symbol, onValueChange = { symbol = it.uppercase() }, label = { Text(stringResource(R.string.order_symbol)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = side == "BUY", onClick = { side = "BUY" }, label = { Text(stringResource(R.string.order_buy)) })
                        FilterChip(selected = side == "SELL", onClick = { side = "SELL" }, label = { Text(stringResource(R.string.order_sell)) })
                    }
                    OutlinedTextField(value = qty, onValueChange = { qty = it }, label = { Text(stringResource(R.string.order_quantity)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = price, onValueChange = { price = it }, label = { Text(stringResource(R.string.order_price)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
            },
            confirmButton = {
                Button(onClick = {
                    viewModel.createOrder(symbol, side, qty.toIntOrNull() ?: 0, price.toDoubleOrNull())
                    showOrderForm = false
                }) { Text(stringResource(R.string.confirm)) }
            },
            dismissButton = { TextButton(onClick = { showOrderForm = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}
