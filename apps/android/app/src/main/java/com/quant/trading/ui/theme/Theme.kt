package com.quant.trading.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val DarkColorScheme = darkColorScheme(
    primary = Blue500,
    onPrimary = TextPrimaryDark,
    primaryContainer = Blue600,
    secondary = Blue400,
    background = SurfaceDark,
    surface = SurfaceDarkMid,
    surfaceVariant = SurfaceDarkLight,
    onBackground = TextPrimaryDark,
    onSurface = TextPrimaryDark,
    onSurfaceVariant = TextSecondaryDark,
    error = Danger,
    onError = TextPrimaryDark,
)

private val LightColorScheme = lightColorScheme(
    primary = Blue600,
    onPrimary = SurfaceLight,
    primaryContainer = Blue500,
    secondary = Blue400,
    background = SurfaceLight,
    surface = SurfaceLight,
    surfaceVariant = SurfaceLightMid,
    onBackground = TextPrimaryLight,
    onSurface = TextPrimaryLight,
    onSurfaceVariant = TextSecondaryLight,
    error = Danger,
    onError = SurfaceLight,
)

@Composable
fun QuantTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography(),
        content = content,
    )
}
