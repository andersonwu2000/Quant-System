package com.quant.trading.ui.screens.login

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.quant.trading.R

@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    viewModel: LoginViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = stringResource(R.string.app_name),
            style = MaterialTheme.typography.headlineMedium,
        )

        Spacer(Modifier.height(8.dp))

        Text(
            text = stringResource(R.string.login_title),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(32.dp))

        // Server URL
        OutlinedTextField(
            value = state.serverUrl,
            onValueChange = viewModel::updateServerUrl,
            label = { Text(stringResource(R.string.login_server_url)) },
            placeholder = { Text(stringResource(R.string.login_server_hint)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        Spacer(Modifier.height(16.dp))

        // Mode toggle
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
        ) {
            FilterChip(
                selected = !state.usePassword,
                onClick = { if (state.usePassword) viewModel.toggleMode() },
                label = { Text(stringResource(R.string.login_mode_apikey)) },
            )
            Spacer(Modifier.width(8.dp))
            FilterChip(
                selected = state.usePassword,
                onClick = { if (!state.usePassword) viewModel.toggleMode() },
                label = { Text(stringResource(R.string.login_mode_password)) },
            )
        }

        Spacer(Modifier.height(16.dp))

        if (state.usePassword) {
            OutlinedTextField(
                value = state.username,
                onValueChange = viewModel::updateUsername,
                label = { Text(stringResource(R.string.login_username)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = state.password,
                onValueChange = viewModel::updatePassword,
                label = { Text(stringResource(R.string.login_password)) },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                modifier = Modifier.fillMaxWidth(),
            )
        } else {
            OutlinedTextField(
                value = state.apiKey,
                onValueChange = viewModel::updateApiKey,
                label = { Text(stringResource(R.string.login_api_key)) },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
            )
        }

        Spacer(Modifier.height(24.dp))

        // Error
        state.error?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(8.dp))
        }

        // Login button
        Button(
            onClick = { viewModel.login(onLoginSuccess) },
            enabled = !state.loading,
            modifier = Modifier.fillMaxWidth().height(48.dp),
        ) {
            if (state.loading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary,
                )
            } else {
                Text(stringResource(R.string.login_button))
            }
        }
    }
}
