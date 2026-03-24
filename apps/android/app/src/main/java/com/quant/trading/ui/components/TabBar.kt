package com.quant.trading.ui.components

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

data class TabItem(val id: String, val label: String)

@Composable
fun TabBar(
    tabs: List<TabItem>,
    activeTab: String,
    onTabChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    TabRow(
        selectedTabIndex = tabs.indexOfFirst { it.id == activeTab }.coerceAtLeast(0),
        modifier = modifier,
    ) {
        tabs.forEach { tab ->
            Tab(
                selected = tab.id == activeTab,
                onClick = { onTabChange(tab.id) },
                text = { Text(tab.label) },
            )
        }
    }
}
