package com.quant.trading

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.quant.trading.navigation.QuantNavHost
import com.quant.trading.ui.theme.QuantTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // Pass null to prevent restoring stale Compose/Navigation state after process death.
        // Without this, Android tries to restore the previous screen's state which can crash
        // if EncryptedSharedPreferences or ViewModel init fails during restoration.
        super.onCreate(null)
        enableEdgeToEdge()
        setContent {
            QuantTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    QuantNavHost()
                }
            }
        }
    }
}
