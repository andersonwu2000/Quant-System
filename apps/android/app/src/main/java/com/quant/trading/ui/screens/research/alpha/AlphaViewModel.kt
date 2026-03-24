package com.quant.trading.ui.screens.research.alpha

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AlphaViewModel @Inject constructor(
    private val api: QuantApiService,
) : ViewModel() {

    data class UiState(
        val universe: String = "AAPL,MSFT,GOOGL,AMZN,META",
        val startDate: String = "2023-01-01",
        val endDate: String = "2024-12-31",
        val running: Boolean = false,
        val report: AlphaReport? = null,
        val error: String? = null,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    fun updateUniverse(v: String) { _state.value = _state.value.copy(universe = v) }
    fun updateStartDate(v: String) { _state.value = _state.value.copy(startDate = v) }
    fun updateEndDate(v: String) { _state.value = _state.value.copy(endDate = v) }

    fun run() {
        val s = _state.value
        if (s.running) return
        _state.value = s.copy(running = true, error = null, report = null)

        viewModelScope.launch {
            try {
                val symbols = s.universe.split(",").map { it.trim() }.filter { it.isNotBlank() }
                val req = AlphaRunRequest(
                    factors = listOf(
                        AlphaFactorSpec("momentum", 1),
                        AlphaFactorSpec("mean_reversion", -1),
                        AlphaFactorSpec("volatility", -1),
                    ),
                    universe = symbols,
                    start = s.startDate,
                    end = s.endDate,
                )
                val summary = api.runAlpha(req)
                pollResult(summary.taskId)
            } catch (e: Exception) {
                _state.value = _state.value.copy(running = false, error = e.message)
            }
        }
    }

    private suspend fun pollResult(taskId: String) {
        while (true) {
            delay(2000)
            try {
                val status = api.alphaStatus(taskId)
                when (status.status) {
                    "completed" -> {
                        val report = api.alphaResult(taskId)
                        _state.value = _state.value.copy(running = false, report = report)
                        return
                    }
                    "failed" -> {
                        _state.value = _state.value.copy(running = false, error = status.error ?: "Alpha run failed")
                        return
                    }
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(running = false, error = e.message)
                return
            }
        }
    }
}
