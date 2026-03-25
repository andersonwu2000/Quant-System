package com.quant.trading.data.api

import com.quant.trading.data.local.SecureStorage
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * OkHttp interceptor that dynamically rewrites the request URL base
 * to match the server URL stored in SecureStorage.
 *
 * This fixes the issue where Retrofit is a Singleton created once at app start,
 * but the user can change the server URL on the login screen.
 */
@Singleton
class DynamicBaseUrlInterceptor @Inject constructor(
    private val storage: SecureStorage,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val serverUrl = storage.getServerUrl()

        if (serverUrl.isNullOrBlank()) {
            return chain.proceed(original)
        }

        val newBaseUrl = serverUrl.trimEnd('/').toHttpUrlOrNull() ?: return chain.proceed(original)

        val newUrl = original.url.newBuilder()
            .scheme(newBaseUrl.scheme)
            .host(newBaseUrl.host)
            .port(newBaseUrl.port)
            .build()

        val newRequest = original.newBuilder()
            .url(newUrl)
            .build()

        return chain.proceed(newRequest)
    }
}
