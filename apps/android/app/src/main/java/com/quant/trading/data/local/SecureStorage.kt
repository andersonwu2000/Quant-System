package com.quant.trading.data.local

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Encrypted credential storage backed by Android Keystore.
 */
@Singleton
class SecureStorage @Inject constructor(
    @ApplicationContext context: Context,
) {
    companion object {
        private const val PREFS_NAME = "quant_secure_prefs"
        private const val KEY_JWT = "jwt_token"
        private const val KEY_API_KEY = "api_key"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_LANG = "quant_lang"
        private const val KEY_THEME = "quant_theme"
    }

    private val prefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    // ── JWT ─────────────────────────────────────────────────────────────────

    fun getJwt(): String? = prefs.getString(KEY_JWT, null)

    fun setJwt(token: String) = prefs.edit().putString(KEY_JWT, token).apply()

    fun clearJwt() = prefs.edit().remove(KEY_JWT).apply()

    /**
     * Extract role from JWT payload (base64-decoded, no verification).
     * Returns "viewer" as fallback.
     */
    fun extractRole(): String {
        val token = getJwt() ?: return "viewer"
        return try {
            val parts = token.split(".")
            if (parts.size < 2) return "viewer"
            val payload = String(Base64.decode(parts[1], Base64.URL_SAFE or Base64.NO_PADDING))
            val json = Json.parseToJsonElement(payload).jsonObject
            json["role"]?.jsonPrimitive?.content ?: "viewer"
        } catch (_: Exception) {
            "viewer"
        }
    }

    fun isAuthenticated(): Boolean = !getJwt().isNullOrBlank() || !getApiKey().isNullOrBlank()

    // ── API Key ─────────────────────────────────────────────────────────────

    fun getApiKey(): String? = prefs.getString(KEY_API_KEY, null)

    fun setApiKey(key: String) = prefs.edit().putString(KEY_API_KEY, key).apply()

    // ── Server URL ──────────────────────────────────────────────────────────

    fun getServerUrl(): String? = prefs.getString(KEY_SERVER_URL, null)

    fun setServerUrl(url: String) = prefs.edit().putString(KEY_SERVER_URL, url.trimEnd('/')).apply()

    // ── Preferences ─────────────────────────────────────────────────────────

    fun getLang(): String = prefs.getString(KEY_LANG, "en") ?: "en"

    fun setLang(lang: String) = prefs.edit().putString(KEY_LANG, lang).apply()

    fun getTheme(): String = prefs.getString(KEY_THEME, "system") ?: "system"

    fun setTheme(theme: String) = prefs.edit().putString(KEY_THEME, theme).apply()

    // ── Clear all ───────────────────────────────────────────────────────────

    fun clearAll() = prefs.edit().clear().apply()
}
