package com.quant.trading.navigation

import androidx.lifecycle.ViewModel
import com.quant.trading.data.local.SecureStorage
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

/**
 * Simple ViewModel to expose SecureStorage for NavGraph auth checks.
 */
@HiltViewModel
class NavViewModel @Inject constructor(
    val storage: SecureStorage,
) : ViewModel()
