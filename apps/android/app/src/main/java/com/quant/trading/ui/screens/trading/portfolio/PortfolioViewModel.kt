package com.quant.trading.ui.screens.trading.portfolio

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.PortfolioCreateRequest
import com.quant.trading.data.api.PortfolioListItem
import com.quant.trading.data.api.QuantApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class PortfolioViewModel @Inject constructor(
    private val api: QuantApiService,
) : ViewModel() {

    data class UiState(
        val portfolios: List<PortfolioListItem> = emptyList(),
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
                val resp = api.listSavedPortfolios()
                _state.value = _state.value.copy(portfolios = resp.portfolios, loading = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message)
            }
        }
    }

    fun create(name: String, initialCash: Double) {
        viewModelScope.launch {
            try {
                api.createSavedPortfolio(PortfolioCreateRequest(name, initialCash))
                load()
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message ?: "Failed to create portfolio")
            }
        }
    }

    fun delete(id: String) {
        viewModelScope.launch {
            try {
                api.deleteSavedPortfolio(id)
                load()
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message ?: "Failed to delete portfolio")
            }
        }
    }
}
