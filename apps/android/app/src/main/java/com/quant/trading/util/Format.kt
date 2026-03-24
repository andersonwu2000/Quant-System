package com.quant.trading.util

import java.text.NumberFormat
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Formatting utilities — mirrors apps/shared/src/utils/format.ts
 */
object Format {

    private val currencyFmt = NumberFormat.getCurrencyInstance(Locale.US)
    private val dateFmt = DateTimeFormatter.ofPattern("yyyy-MM-dd")
    private val timeFmt = DateTimeFormatter.ofPattern("HH:mm:ss")

    /** Format as USD currency: $1,234.56 */
    fun currency(value: Double): String = currencyFmt.format(value)

    /** Format as percentage: 12.34% */
    fun pct(value: Double, decimals: Int = 2): String =
        "%.${decimals}f%%".format(value * 100)

    /** Format price with auto decimals. */
    fun price(value: Double): String = when {
        value >= 1000 -> "%.0f".format(value)
        value >= 1 -> "%.2f".format(value)
        else -> "%.4f".format(value)
    }

    /** Format large number with K/M/B suffix. */
    fun num(value: Double): String = when {
        value >= 1_000_000_000 -> "%.1fB".format(value / 1_000_000_000)
        value >= 1_000_000 -> "%.1fM".format(value / 1_000_000)
        value >= 1_000 -> "%.1fK".format(value / 1_000)
        else -> "%.0f".format(value)
    }

    /** Format ISO date string to yyyy-MM-dd. */
    fun date(isoString: String): String = try {
        val instant = Instant.parse(isoString)
        dateFmt.format(instant.atZone(ZoneId.systemDefault()))
    } catch (_: Exception) {
        isoString.take(10)
    }

    /** Format ISO timestamp to HH:mm:ss. */
    fun time(isoString: String): String = try {
        val instant = Instant.parse(isoString)
        timeFmt.format(instant.atZone(ZoneId.systemDefault()))
    } catch (_: Exception) {
        isoString
    }

    /** Format uptime seconds to human readable string. */
    fun uptime(seconds: Double): String {
        val totalSec = seconds.toLong()
        val h = totalSec / 3600
        val m = (totalSec % 3600) / 60
        val s = totalSec % 60
        return "${h}h ${m}m ${s}s"
    }
}
