package com.quant.trading.ui.screens.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.Portfolio
import com.quant.trading.data.api.QuantApiService
import com.quant.trading.data.api.WebSocketManager
import com.quant.trading.data.api.WebSocketManager.Channel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val api: QuantApiService,
    private val ws: WebSocketManager,
) : ViewModel() {

    data class UiState(
        val portfolio: Portfolio? = null,
        val loading: Boolean = true,
        val error: String? = null,
        val wsConnected: Boolean = false,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    init {
        loadPortfolio()
        connectWs()
    }

    fun loadPortfolio() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val p = api.getPortfolio()
                _state.value = _state.value.copy(portfolio = p, loading = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message)
            }
        }
    }

    private fun connectWs() {
        ws.connect(Channel.PORTFOLIO)
        _state.value = _state.value.copy(wsConnected = true)

        viewModelScope.launch {
            ws.messages
                .filter { it.channel == Channel.PORTFOLIO }
                .collect {
                    // On WS update, refresh portfolio data
                    loadPortfolio()
                }
        }
    }

    override fun onCleared() {
        ws.disconnect(Channel.PORTFOLIO)
        super.onCleared()
    }
}
