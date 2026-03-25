package com.quant.trading.ui.screens.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.LoginRequest
import com.quant.trading.data.api.QuantApiService
import com.quant.trading.data.local.SecureStorage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val api: QuantApiService,
    private val storage: SecureStorage,
) : ViewModel() {

    data class UiState(
        val serverUrl: String = "",
        val apiKey: String = "",
        val username: String = "",
        val password: String = "",
        val usePassword: Boolean = true,
        val loading: Boolean = false,
        val error: String? = null,
    )

    private val _state = MutableStateFlow(
        UiState(serverUrl = storage.getServerUrl() ?: "http://10.0.2.2:8000")
    )
    val state: StateFlow<UiState> = _state

    fun updateServerUrl(url: String) { _state.value = _state.value.copy(serverUrl = url) }
    fun updateApiKey(key: String) { _state.value = _state.value.copy(apiKey = key) }
    fun updateUsername(v: String) { _state.value = _state.value.copy(username = v) }
    fun updatePassword(v: String) { _state.value = _state.value.copy(password = v) }
    fun toggleMode() { _state.value = _state.value.copy(usePassword = !_state.value.usePassword) }

    fun login(onSuccess: () -> Unit) {
        val s = _state.value
        if (s.loading) return

        _state.value = s.copy(loading = true, error = null)
        storage.setServerUrl(s.serverUrl)

        viewModelScope.launch {
            try {
                val body = if (s.usePassword) {
                    LoginRequest(username = s.username, password = s.password)
                } else {
                    LoginRequest(apiKey = s.apiKey)
                }

                val resp = api.login(body)
                storage.setJwt(resp.accessToken)
                if (!s.usePassword) storage.setApiKey(s.apiKey)
                _state.value = _state.value.copy(loading = false)
                onSuccess()
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    loading = false,
                    error = e.message ?: "Login failed",
                )
            }
        }
    }
}
