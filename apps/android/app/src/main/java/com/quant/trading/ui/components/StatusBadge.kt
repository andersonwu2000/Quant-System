package com.quant.trading.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.quant.trading.ui.theme.*

@Composable
fun StatusBadge(
    text: String,
    modifier: Modifier = Modifier,
) {
    val (bg, fg) = when (text.lowercase()) {
        "running", "active", "connected", "filled", "completed" -> Success.copy(alpha = 0.15f) to Success
        "stopped", "inactive", "disconnected", "failed" -> Danger.copy(alpha = 0.15f) to Danger
        "open", "pending", "running…" -> Warning.copy(alpha = 0.15f) to Warning
        else -> MaterialTheme.colorScheme.surfaceVariant to MaterialTheme.colorScheme.onSurfaceVariant
    }

    Text(
        text = text,
        style = MaterialTheme.typography.labelSmall,
        fontWeight = FontWeight.SemiBold,
        color = fg,
        modifier = modifier
            .clip(RoundedCornerShape(4.dp))
            .background(bg)
            .padding(horizontal = 8.dp, vertical = 2.dp),
    )
}
