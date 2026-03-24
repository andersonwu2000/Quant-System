package com.quant.trading.ui.components

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import com.quant.trading.ui.theme.PnlNegative
import com.quant.trading.ui.theme.PnlNeutral
import com.quant.trading.ui.theme.PnlPositive

@Composable
fun PnlText(
    value: Double,
    formatted: String,
    modifier: Modifier = Modifier,
    style: TextStyle = MaterialTheme.typography.bodyMedium,
) {
    val color = when {
        value > 0 -> PnlPositive
        value < 0 -> PnlNegative
        else -> PnlNeutral
    }
    val prefix = if (value > 0) "+" else ""
    Text(
        text = "$prefix$formatted",
        color = color,
        style = style,
        modifier = modifier,
    )
}
