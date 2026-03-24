package com.quant.trading.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.BookmarkBorder
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Science
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ShieldMoon
import androidx.compose.material.icons.filled.SwapHoriz
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * All navigation destinations in the app.
 */
sealed class Screen(
    val route: String,
    val icon: ImageVector,
    val label: String,
) {
    data object Dashboard : Screen("dashboard", Icons.Default.Dashboard, "Dashboard")
    data object Trading : Screen("trading", Icons.Default.SwapHoriz, "Trading")
    data object Strategies : Screen("strategies", Icons.Default.AutoGraph, "Strategies")
    data object Research : Screen("research", Icons.Default.Science, "Research")
    data object Risk : Screen("risk", Icons.Default.ShieldMoon, "Risk")
    data object Guide : Screen("guide", Icons.Default.MenuBook, "Guide")
    data object Settings : Screen("settings", Icons.Default.Settings, "Settings")
    data object Admin : Screen("admin", Icons.Default.AdminPanelSettings, "Admin")
    data object Login : Screen("login", Icons.Default.BookmarkBorder, "Login")

    companion object {
        /** Primary bottom nav items (max 5). */
        val primaryTabs = listOf(Dashboard, Trading, Strategies, Research, Risk)
        /** Items shown in the "More" overflow. */
        val moreTabs = listOf(Guide, Settings, Admin)
    }
}
