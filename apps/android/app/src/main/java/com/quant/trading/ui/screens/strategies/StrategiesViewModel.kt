package com.quant.trading.ui.screens.strategies

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.QuantApiService
import com.quant.trading.data.api.StrategyInfo
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class StrategiesViewModel @Inject constructor(
    private val api: QuantApiService,
) : ViewModel() {

    data class UiState(
        val strategies: List<StrategyInfo> = emptyList(),
        val loading: Boolean = true,
        val error: String? = null,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    init { load() }

    fun load() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val resp = api.listStrategies()
                _state.value = _state.value.copy(strategies = resp.strategies, loading = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message)
            }
        }
    }

    fun start(name: String) {
        viewModelScope.launch {
            try { api.startStrategy(name); load() } catch (_: Exception) {}
        }
    }

    fun stop(name: String) {
        viewModelScope.launch {
            try { api.stopStrategy(name); load() } catch (_: Exception) {}
        }
    }
}
