package com.quant.trading.ui.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.quant.trading.R
import com.quant.trading.data.*
import com.quant.trading.ui.theme.Blue400
import com.quant.trading.ui.theme.Blue500
import java.util.Locale

/**
 * Full-screen bottom sheet for selecting stocks.
 * Mirrors the web frontend's UniversePicker with:
 * - 3 market tabs (US / TW / ETF)
 * - Search by ticker or company name
 * - Sector grouping
 * - Preset quick-select buttons
 * - Select all / Clear bulk actions
 * - Section-level toggle
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class, ExperimentalFoundationApi::class)
@Composable
fun UniversePickerSheet(
    selected: List<String>,
    onConfirm: (List<String>) -> Unit,
    onDismiss: () -> Unit,
) {
    // Local mutable copy so changes only apply on "Done"
    var localSelected by remember { mutableStateOf(selected.toMutableList()) }
    var marketTab by remember { mutableStateOf(Market.US) }
    var query by remember { mutableStateOf("") }

    val isZh = remember {
        Locale.getDefault().language == "zh"
    }

    // Filtered stocks for current tab + query
    val filtered = remember(marketTab, query) {
        val q = query.trim().lowercase()
        STOCK_LIST.filter { s ->
            s.market == marketTab && (q.isEmpty() ||
                s.ticker.lowercase().contains(q) ||
                s.name.lowercase().contains(q) ||
                (s.sector ?: "").lowercase().contains(q))
        }
    }

    // Group by sector
    val grouped = remember(filtered) {
        filtered.groupBy { it.sector ?: "Other" }
            .toList()
            .sortedBy { (sector, _) -> sector }
    }

    val checkedInView = filtered.count { it.ticker in localSelected }

    // Presets for current market tab
    val visiblePresets = remember(marketTab) {
        PRESETS.filter { it.key.startsWith(marketTab.name.lowercase()) }
    }

    val tabCounts = remember {
        mapOf(
            Market.US to STOCK_LIST.count { it.market == Market.US },
            Market.TW to STOCK_LIST.count { it.market == Market.TW },
            Market.ETF to STOCK_LIST.count { it.market == Market.ETF },
        )
    }

    val sheetState = rememberModalBottomSheetState(
        skipPartiallyExpanded = true,
        confirmValueChange = { it != SheetValue.Hidden },
    )

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        dragHandle = null,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding(),
        ) {
            // ── Header ──────────────────────────────────────────────
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.universe_picker_title),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = stringResource(R.string.close))
                }
            }

            // ── Market tabs ─────────────────────────────────────────
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Market.entries.forEach { tab ->
                    val isActive = marketTab == tab
                    val label = when (tab) {
                        Market.US -> if (isZh) "美股" else "US"
                        Market.TW -> if (isZh) "台股" else "TW"
                        Market.ETF -> "ETF"
                    }
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(6.dp))
                            .background(
                                if (isActive) MaterialTheme.colorScheme.surface
                                else MaterialTheme.colorScheme.surfaceVariant,
                            )
                            .clickable { marketTab = tab; query = "" }
                            .padding(vertical = 8.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = "$label (${tabCounts[tab]})",
                            fontSize = 13.sp,
                            fontWeight = if (isActive) FontWeight.SemiBold else FontWeight.Normal,
                            color = if (isActive) MaterialTheme.colorScheme.onSurface
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            // ── Presets ─────────────────────────────────────────────
            if (visiblePresets.isNotEmpty()) {
                FlowRow(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    visiblePresets.forEach { preset ->
                        SuggestionChip(
                            onClick = { localSelected = preset.tickers.toMutableList() },
                            label = {
                                Text(
                                    text = if (isZh) preset.labelZh else preset.label,
                                    fontSize = 11.sp,
                                )
                            },
                            shape = RoundedCornerShape(6.dp),
                        )
                    }
                }
                Spacer(Modifier.height(8.dp))
            }

            // ── Search + bulk actions ───────────────────────────────
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    placeholder = { Text(stringResource(R.string.universe_search), fontSize = 13.sp) },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, modifier = Modifier.size(18.dp)) },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                    textStyle = MaterialTheme.typography.bodySmall,
                    shape = RoundedCornerShape(8.dp),
                )
                // Select all filtered
                TextButton(
                    onClick = {
                        val tickers = filtered.map { it.ticker }
                        localSelected = (localSelected + tickers).distinct().toMutableList()
                    },
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                ) {
                    Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(2.dp))
                    Text(if (isZh) "全選" else "All", fontSize = 11.sp)
                }
                // Clear filtered
                TextButton(
                    onClick = {
                        val tickerSet = filtered.map { it.ticker }.toSet()
                        localSelected = localSelected.filter { it !in tickerSet }.toMutableList()
                    },
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(2.dp))
                    Text(if (isZh) "清除" else "Clear", fontSize = 11.sp)
                }
            }

            // ── Selection count ─────────────────────────────────────
            Text(
                text = buildString {
                    append("$checkedInView / ${filtered.size} ")
                    append(stringResource(R.string.universe_selected))
                    if (localSelected.size != checkedInView) {
                        append("  (")
                        append(if (isZh) "總計" else "total")
                        append(": ${localSelected.size})")
                    }
                },
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp),
            )

            HorizontalDivider(modifier = Modifier.padding(top = 4.dp))

            // ── Stock list (grouped by sector) ──────────────────────
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            ) {
                if (grouped.isEmpty()) {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 40.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                text = if (isZh) "無符合結果" else "No matches",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }

                grouped.forEach { (sector, stocks) ->
                    // Sticky sector header
                    stickyHeader(key = "header_$sector") {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(MaterialTheme.colorScheme.surface)
                                .padding(vertical = 6.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = "$sector (${stocks.size})",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                letterSpacing = 0.5.sp,
                            )
                            // Section-level toggle
                            val allChecked = stocks.all { it.ticker in localSelected }
                            TextButton(
                                onClick = {
                                    val tickers = stocks.map { it.ticker }
                                    localSelected = if (allChecked) {
                                        val tickerSet = tickers.toSet()
                                        localSelected.filter { it !in tickerSet }.toMutableList()
                                    } else {
                                        (localSelected + tickers).distinct().toMutableList()
                                    }
                                },
                                contentPadding = PaddingValues(horizontal = 6.dp, vertical = 2.dp),
                            ) {
                                Text(
                                    text = if (allChecked) {
                                        if (isZh) "取消" else "−"
                                    } else {
                                        if (isZh) "全選" else "+"
                                    },
                                    fontSize = 10.sp,
                                )
                            }
                        }
                    }

                    // Stock items
                    items(
                        items = stocks,
                        key = { it.ticker },
                    ) { stock ->
                        val checked = stock.ticker in localSelected
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(6.dp))
                                .background(
                                    if (checked) Blue500.copy(alpha = 0.08f)
                                    else MaterialTheme.colorScheme.surface,
                                )
                                .clickable {
                                    localSelected = if (checked) {
                                        localSelected.filter { it != stock.ticker }.toMutableList()
                                    } else {
                                        (localSelected + stock.ticker).toMutableList()
                                    }
                                }
                                .padding(horizontal = 8.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Checkbox(
                                checked = checked,
                                onCheckedChange = { isChecked ->
                                    localSelected = if (isChecked) {
                                        (localSelected + stock.ticker).toMutableList()
                                    } else {
                                        localSelected.filter { it != stock.ticker }.toMutableList()
                                    }
                                },
                                modifier = Modifier.size(20.dp),
                                colors = CheckboxDefaults.colors(checkedColor = Blue500),
                            )
                            Text(
                                text = stock.ticker.replace(".TW", ""),
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium,
                                color = MaterialTheme.colorScheme.onSurface,
                            )
                            Text(
                                text = stock.name,
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f),
                            )
                        }
                    }
                }
            }

            // ── Footer ──────────────────────────────────────────────
            HorizontalDivider()
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "${localSelected.size} ${stringResource(R.string.universe_selected)}",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(
                    onClick = { onConfirm(localSelected.toList()) },
                    shape = RoundedCornerShape(8.dp),
                ) {
                    Text(stringResource(R.string.universe_done))
                }
            }
        }
    }
}

/**
 * Compact trigger chip that shows selected count and opens the picker.
 * Replaces the old plain-text OutlinedTextField.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun UniversePickerField(
    selected: List<String>,
    onOpenPicker: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val isZh = remember { Locale.getDefault().language == "zh" }

    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = stringResource(R.string.backtest_universe),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedCard(
            onClick = onOpenPicker,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(8.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (selected.isEmpty()) {
                    Text(
                        text = stringResource(R.string.universe_search),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 14.sp,
                        modifier = Modifier.weight(1f),
                    )
                } else if (selected.size <= 4) {
                    FlowRow(
                        modifier = Modifier.weight(1f),
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        selected.forEach { ticker ->
                            Surface(
                                shape = RoundedCornerShape(4.dp),
                                color = Blue400.copy(alpha = 0.12f),
                                contentColor = Blue500,
                            ) {
                                Text(
                                    text = ticker.replace(".TW", ""),
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Medium,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                )
                            }
                        }
                    }
                } else {
                    Text(
                        text = "${selected.size} ${stringResource(R.string.universe_selected)}",
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.width(8.dp))
                Icon(
                    Icons.Default.Search,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
