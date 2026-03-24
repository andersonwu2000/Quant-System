package com.quant.trading.ui.screens.trading

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.quant.trading.R
import com.quant.trading.ui.components.TabBar
import com.quant.trading.ui.components.TabItem
import com.quant.trading.ui.screens.trading.orders.OrdersTab
import com.quant.trading.ui.screens.trading.paper.PaperTradingTab
import com.quant.trading.ui.screens.trading.portfolio.PortfolioTab

@Composable
fun TradingScreen() {
    val tabs = listOf(
        TabItem("portfolio", stringResource(R.string.tab_portfolio)),
        TabItem("orders", stringResource(R.string.tab_orders)),
        TabItem("paper-trading", stringResource(R.string.tab_paper_trading)),
    )
    var activeTab by remember { mutableStateOf("portfolio") }

    Column(Modifier.fillMaxSize()) {
        TabBar(tabs = tabs, activeTab = activeTab, onTabChange = { activeTab = it })

        when (activeTab) {
            "portfolio" -> PortfolioTab()
            "orders" -> OrdersTab()
            "paper-trading" -> PaperTradingTab()
        }
    }
}
