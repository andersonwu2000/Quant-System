package com.quant.trading.ui.screens.research.backtest

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.quant.trading.data.api.BacktestRequest
import com.quant.trading.data.api.BacktestResult
import com.quant.trading.data.api.BacktestSummary
import com.quant.trading.data.api.QuantApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class BacktestViewModel @Inject constructor(
    private val api: QuantApiService,
) : ViewModel() {

    data class UiState(
        val strategy: String = "momentum",
        val universe: String = "AAPL,MSFT,GOOGL",
        val startDate: String = "2023-01-01",
        val endDate: String = "2024-12-31",
        val running: Boolean = false,
        val progress: Float = 0f,
        val summary: BacktestSummary? = null,
        val result: BacktestResult? = null,
        val error: String? = null,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    fun updateStrategy(v: String) { _state.value = _state.value.copy(strategy = v) }
    fun updateUniverse(v: String) { _state.value = _state.value.copy(universe = v) }
    fun updateStartDate(v: String) { _state.value = _state.value.copy(startDate = v) }
    fun updateEndDate(v: String) { _state.value = _state.value.copy(endDate = v) }

    fun run() {
        val s = _state.value
        if (s.running) return
        _state.value = s.copy(running = true, error = null, result = null, summary = null, progress = 0f)

        viewModelScope.launch {
            try {
                val symbols = s.universe.split(",").map { it.trim() }.filter { it.isNotBlank() }
                val req = BacktestRequest(
                    strategy = s.strategy,
                    universe = symbols,
                    start = s.startDate,
                    end = s.endDate,
                )
                val summary = api.submitBacktest(req)
                _state.value = _state.value.copy(summary = summary)

                // Poll for completion
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
                val status = api.backtestStatus(taskId)
                val progressVal = if (status.progressTotal != null && status.progressTotal > 0) {
                    (status.progressCurrent ?: 0).toFloat() / status.progressTotal
                } else 0f

                _state.value = _state.value.copy(summary = status, progress = progressVal)

                when (status.status) {
                    "completed" -> {
                        val result = api.backtestResult(taskId)
                        _state.value = _state.value.copy(running = false, result = result)
                        return
                    }
                    "failed" -> {
                        _state.value = _state.value.copy(running = false, error = status.error ?: "Backtest failed")
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
