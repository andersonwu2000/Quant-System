package com.quant.trading.ui.screens.admin

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
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
fun AdminScreen(viewModel: AdminViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    var deleteTarget by remember { mutableStateOf<Int?>(null) }

    if (state.loading && state.users.isEmpty()) { PageSkeleton(); return }
    state.error?.let { ErrorAlert(it, onRetry = viewModel::load); return }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        contentPadding = PaddingValues(vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Text(stringResource(R.string.nav_admin), style = MaterialTheme.typography.headlineSmall)
        }

        item { Text(stringResource(R.string.admin_users), style = MaterialTheme.typography.titleMedium) }

        if (state.users.isEmpty()) {
            item { EmptyState() }
        } else {
            items(state.users) { user ->
                QuantCard {
                    Row(
                        modifier = Modifier.padding(16.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(user.displayName, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(
                                "@${user.username} · ${user.role}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                StatusBadge(if (user.isActive) "Active" else "Inactive")
                                Text(
                                    "Created: ${Format.date(user.createdAt)}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        if (user.username != "admin") {
                            IconButton(onClick = { deleteTarget = user.id }) {
                                Icon(Icons.Default.Delete, contentDescription = stringResource(R.string.delete), tint = MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }
            }
        }
    }

    deleteTarget?.let { id ->
        ConfirmDialog(
            title = stringResource(R.string.delete),
            message = "Delete this user?",
            isDangerous = true,
            onConfirm = { viewModel.deleteUser(id) },
            onDismiss = { deleteTarget = null },
        )
    }
}
