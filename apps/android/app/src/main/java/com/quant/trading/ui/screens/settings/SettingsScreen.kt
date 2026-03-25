package com.quant.trading.ui.screens.settings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.quant.trading.R
import com.quant.trading.ui.components.QuantCard
import com.quant.trading.ui.components.MetricCard
import com.quant.trading.util.Format

@Composable
fun SettingsScreen(
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = stringResource(R.string.nav_settings),
            style = MaterialTheme.typography.headlineSmall,
        )

        // Server URL (read-only)
        QuantCard {
            Column(Modifier.padding(16.dp)) {
                Text(stringResource(R.string.settings_server_url), style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(4.dp))
                Text(state.serverUrl, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(4.dp))
                Text("Role: ${state.role}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }

        // Language
        QuantCard {
            Column(Modifier.padding(16.dp)) {
                Text(stringResource(R.string.settings_language), style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = state.lang == "en", onClick = { viewModel.setLang("en") }, label = { Text("English") })
                    FilterChip(selected = state.lang == "zh", onClick = { viewModel.setLang("zh") }, label = { Text("繁體中文") })
                }
            }
        }

        // Theme
        QuantCard {
            Column(Modifier.padding(16.dp)) {
                Text(stringResource(R.string.settings_theme), style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("light" to R.string.settings_theme_light, "dark" to R.string.settings_theme_dark, "system" to R.string.settings_theme_system).forEach { (key, resId) ->
                        FilterChip(selected = state.theme == key, onClick = { viewModel.setTheme(key) }, label = { Text(stringResource(resId)) })
                    }
                }
            }
        }

        // Change Password
        QuantCard {
            Column(Modifier.padding(16.dp)) {
                Text(stringResource(R.string.settings_change_password), style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = state.passwordCurrent,
                    onValueChange = viewModel::updatePasswordCurrent,
                    label = { Text(stringResource(R.string.settings_current_password)) },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = state.passwordNew,
                    onValueChange = viewModel::updatePasswordNew,
                    label = { Text(stringResource(R.string.settings_new_password)) },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                state.passwordMsg?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.height(4.dp))
                }
                Button(
                    onClick = viewModel::changePassword,
                    enabled = !state.passwordLoading && state.passwordCurrent.isNotBlank() && state.passwordNew.isNotBlank(),
                ) {
                    Text(stringResource(R.string.save))
                }
            }
        }

        // System Metrics
        QuantCard {
            Column(Modifier.padding(16.dp)) {
                Text(stringResource(R.string.settings_system_metrics), style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                if (state.metricsLoading) {
                    CircularProgressIndicator(Modifier.size(24.dp))
                } else {
                    state.metrics?.let { m ->
                        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            MetricCard(label = "Uptime", value = Format.uptime(m.uptimeSeconds), modifier = Modifier.weight(1f))
                            MetricCard(label = "Requests", value = m.totalRequests.toString(), modifier = Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(8.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            MetricCard(label = "WS Conns", value = m.activeWsConnections.toString(), modifier = Modifier.weight(1f))
                            MetricCard(label = "Strategies", value = m.strategiesRunning.toString(), modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }

        // Logout
        OutlinedButton(
            onClick = onLogout,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
        ) {
            Text(stringResource(R.string.logout))
        }
    }
}
