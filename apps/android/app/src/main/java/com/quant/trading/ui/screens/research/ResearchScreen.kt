package com.quant.trading.ui.screens.research

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.quant.trading.R
import com.quant.trading.ui.components.TabBar
import com.quant.trading.ui.components.TabItem
import com.quant.trading.ui.screens.research.allocation.AllocationTab
import com.quant.trading.ui.screens.research.alpha.AlphaTab
import com.quant.trading.ui.screens.research.backtest.BacktestTab

@Composable
fun ResearchScreen() {
    val tabs = listOf(
        TabItem("backtest", stringResource(R.string.tab_backtest)),
        TabItem("alpha", stringResource(R.string.tab_alpha)),
        TabItem("allocation", stringResource(R.string.tab_allocation)),
    )
    var activeTab by remember { mutableStateOf("backtest") }

    Column(Modifier.fillMaxSize()) {
        TabBar(tabs = tabs, activeTab = activeTab, onTabChange = { activeTab = it })

        when (activeTab) {
            "backtest" -> BacktestTab()
            "alpha" -> AlphaTab()
            "allocation" -> AllocationTab()
        }
    }
}
