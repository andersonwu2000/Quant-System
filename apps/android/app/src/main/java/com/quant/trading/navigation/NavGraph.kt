package com.quant.trading.navigation

import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.*
import com.quant.trading.data.local.SecureStorage
import com.quant.trading.ui.screens.admin.AdminScreen
import com.quant.trading.ui.screens.dashboard.DashboardScreen
import com.quant.trading.ui.screens.guide.GuideScreen
import com.quant.trading.ui.screens.login.LoginScreen
import com.quant.trading.ui.screens.research.ResearchScreen
import com.quant.trading.ui.screens.risk.RiskScreen
import com.quant.trading.ui.screens.settings.SettingsScreen
import com.quant.trading.ui.screens.strategies.StrategiesScreen
import com.quant.trading.ui.screens.trading.TradingScreen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuantNavHost() {
    val navViewModel: NavViewModel = hiltViewModel()
    val storage = navViewModel.storage
    val navController = rememberNavController()
    val startDest = if (storage.isAuthenticated()) Screen.Dashboard.route else Screen.Login.route
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute != null && currentRoute != Screen.Login.route

    Scaffold(
        contentWindowInsets = WindowInsets.systemBars,
        bottomBar = {
            if (showBottomBar) {
                BottomNavBar(
                    currentRoute = currentRoute,
                    role = storage.extractRole(),
                    onNavigate = { screen ->
                        navController.navigate(screen.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                )
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = startDest,
            modifier = Modifier.padding(innerPadding),
            enterTransition = {
                slideIntoContainer(AnimatedContentTransitionScope.SlideDirection.Start, tween(250))
            },
            exitTransition = {
                slideOutOfContainer(AnimatedContentTransitionScope.SlideDirection.Start, tween(250))
            },
        ) {
            composable(Screen.Login.route) {
                LoginScreen(
                    onLoginSuccess = {
                        navController.navigate(Screen.Dashboard.route) {
                            popUpTo(Screen.Login.route) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.Dashboard.route) { DashboardScreen() }
            composable(Screen.Trading.route) { TradingScreen() }
            composable(Screen.Strategies.route) { StrategiesScreen() }
            composable(Screen.Research.route) { ResearchScreen() }
            composable(Screen.Risk.route) { RiskScreen() }
            composable(Screen.Guide.route) { GuideScreen() }
            composable(Screen.Settings.route) {
                SettingsScreen(
                    onLogout = {
                        storage.clearAll()
                        navController.navigate(Screen.Login.route) {
                            popUpTo(0) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.Admin.route) { AdminScreen() }
        }
    }
}

@Composable
private fun BottomNavBar(
    currentRoute: String?,
    role: String,
    onNavigate: (Screen) -> Unit,
) {
    var showMore by remember { mutableStateOf(false) }

    NavigationBar(tonalElevation = 2.dp) {
        Screen.primaryTabs.filterNotNull().forEach { screen ->
            NavigationBarItem(
                icon = { Icon(screen.icon, contentDescription = screen.label) },
                label = {
                    Text(
                        text = screen.label,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                selected = currentRoute == screen.route,
                onClick = { onNavigate(screen) },
            )
        }

        // "More" overflow
        NavigationBarItem(
            icon = {
                Box {
                    Icon(Icons.Default.MoreVert, contentDescription = "More")
                    DropdownMenu(
                        expanded = showMore,
                        onDismissRequest = { showMore = false },
                    ) {
                        Screen.moreTabs
                            .filterNotNull()
                            .filter { it != Screen.Admin || role == "admin" }
                            .forEach { screen ->
                                DropdownMenuItem(
                                    text = { Text(screen.label) },
                                    leadingIcon = { Icon(screen.icon, contentDescription = null) },
                                    onClick = {
                                        showMore = false
                                        onNavigate(screen)
                                    },
                                )
                            }
                    }
                }
            },
            label = {
                Text(
                    text = "More",
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            },
            selected = Screen.moreTabs.filterNotNull().any { it.route == currentRoute },
            onClick = { showMore = !showMore },
        )
    }
}
