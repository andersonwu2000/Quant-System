package com.quant.trading.ui.screens.risk

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.*
import com.quant.trading.data.local.SecureStorage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class RiskViewModel @Inject constructor(
    private val api: QuantApiService,
    private val ws: WebSocketManager,
    private val storage: SecureStorage,
) : ViewModel() {

    data class UiState(
        val rules: List<RiskRule> = emptyList(),
        val alerts: List<RiskAlert> = emptyList(),
        val loading: Boolean = true,
        val error: String? = null,
        val role: String = "viewer",
    )

    private val _state = MutableStateFlow(UiState(role = storage.extractRole()))
    val state: StateFlow<UiState> = _state

    init {
        load()
        ws.connect(WebSocketManager.Channel.ALERTS)
        viewModelScope.launch {
            ws.messages.filter { it.channel == WebSocketManager.Channel.ALERTS }.collect { load() }
        }
    }

    fun load() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val rules = api.riskRules()
                val alerts = api.riskAlerts()
                _state.value = _state.value.copy(rules = rules, alerts = alerts, loading = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message)
            }
        }
    }

    fun toggleRule(name: String, enabled: Boolean) {
        viewModelScope.launch {
            try { api.toggleRiskRule(name, RiskRuleToggle(enabled)); load() } catch (_: Exception) {}
        }
    }

    fun killSwitch() {
        viewModelScope.launch {
            try { api.killSwitch(); load() } catch (_: Exception) {}
        }
    }

    override fun onCleared() {
        ws.disconnect(WebSocketManager.Channel.ALERTS)
        super.onCleared()
    }
}
