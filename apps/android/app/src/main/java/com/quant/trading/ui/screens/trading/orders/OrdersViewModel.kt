package com.quant.trading.ui.screens.trading.orders

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.ManualOrderRequest
import com.quant.trading.data.api.OrderInfo
import com.quant.trading.data.api.QuantApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class OrdersViewModel @Inject constructor(
    private val api: QuantApiService,
) : ViewModel() {

    data class UiState(
        val orders: List<OrderInfo> = emptyList(),
        val loading: Boolean = true,
        val error: String? = null,
        val filter: String? = null,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    init { load() }

    fun setFilter(f: String?) {
        _state.value = _state.value.copy(filter = f)
        load()
    }

    fun load() {
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val orders = api.listOrders(status = _state.value.filter)
                _state.value = _state.value.copy(orders = orders, loading = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message)
            }
        }
    }

    fun createOrder(symbol: String, side: String, quantity: Int, price: Double?) {
        viewModelScope.launch {
            try {
                api.createOrder(ManualOrderRequest(symbol, side, quantity, price))
                load()
            } catch (_: Exception) {}
        }
    }
}
