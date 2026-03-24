package com.quant.trading.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.ChangePasswordRequest
import com.quant.trading.data.api.QuantApiService
import com.quant.trading.data.api.SystemMetrics
import com.quant.trading.data.local.SecureStorage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val api: QuantApiService,
    val storage: SecureStorage,
) : ViewModel() {

    data class UiState(
        val lang: String = "en",
        val theme: String = "system",
        val serverUrl: String = "",
        val role: String = "viewer",
        val metrics: SystemMetrics? = null,
        val metricsLoading: Boolean = false,
        val passwordCurrent: String = "",
        val passwordNew: String = "",
        val passwordMsg: String? = null,
        val passwordLoading: Boolean = false,
    )

    private val _state = MutableStateFlow(
        UiState(
            lang = storage.getLang(),
            theme = storage.getTheme(),
            serverUrl = storage.getServerUrl() ?: "",
            role = storage.extractRole(),
        )
    )
    val state: StateFlow<UiState> = _state

    init {
        loadMetrics()
    }

    fun setLang(lang: String) {
        storage.setLang(lang)
        _state.value = _state.value.copy(lang = lang)
    }

    fun setTheme(theme: String) {
        storage.setTheme(theme)
        _state.value = _state.value.copy(theme = theme)
    }

    fun updatePasswordCurrent(v: String) { _state.value = _state.value.copy(passwordCurrent = v) }
    fun updatePasswordNew(v: String) { _state.value = _state.value.copy(passwordNew = v) }

    fun changePassword() {
        val s = _state.value
        if (s.passwordLoading) return
        _state.value = s.copy(passwordLoading = true, passwordMsg = null)

        viewModelScope.launch {
            try {
                api.changePassword(
                    ChangePasswordRequest(s.passwordCurrent, s.passwordNew)
                )
                _state.value = _state.value.copy(
                    passwordLoading = false,
                    passwordMsg = "Password changed successfully",
                    passwordCurrent = "",
                    passwordNew = "",
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    passwordLoading = false,
                    passwordMsg = e.message ?: "Failed",
                )
            }
        }
    }

    fun loadMetrics() {
        _state.value = _state.value.copy(metricsLoading = true)
        viewModelScope.launch {
            try {
                val m = api.systemMetrics()
                _state.value = _state.value.copy(metrics = m, metricsLoading = false)
            } catch (_: Exception) {
                _state.value = _state.value.copy(metricsLoading = false)
            }
        }
    }
}
