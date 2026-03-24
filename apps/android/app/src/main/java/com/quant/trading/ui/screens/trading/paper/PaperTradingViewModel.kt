package com.quant.trading.ui.screens.trading.paper

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class PaperTradingViewModel @Inject constructor(
    private val api: QuantApiService,
) : ViewModel() {

    data class UiState(
        val paperStatus: PaperTradingStatus? = null,
        val marketHours: MarketHoursStatus? = null,
        val reconcileResult: ReconcileResult? = null,
        val queuedOrders: QueuedOrdersResponse? = null,
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
                val ps = api.paperTradingStatus()
                val mh = api.marketHours()
                val q = api.queuedOrders()
                _state.value = _state.value.copy(paperStatus = ps, marketHours = mh, queuedOrders = q, loading = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message)
            }
        }
    }

    fun reconcile() {
        viewModelScope.launch {
            try {
                val r = api.reconcile()
                _state.value = _state.value.copy(reconcileResult = r)
            } catch (_: Exception) {}
        }
    }

    fun autoCorrect() {
        viewModelScope.launch {
            try { api.autoCorrect() } catch (_: Exception) {}
        }
    }
}
