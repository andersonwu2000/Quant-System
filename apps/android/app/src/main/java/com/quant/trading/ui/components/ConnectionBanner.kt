package com.quant.trading.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.quant.trading.R
import com.quant.trading.ui.theme.Danger
import com.quant.trading.ui.theme.Success

@Composable
fun ConnectionBanner(
    connected: Boolean,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(visible = !connected, modifier = modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Danger.copy(alpha = 0.15f))
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Text(
                text = stringResource(R.string.disconnected),
                style = MaterialTheme.typography.labelMedium,
                color = Danger,
            )
        }
    }
}
