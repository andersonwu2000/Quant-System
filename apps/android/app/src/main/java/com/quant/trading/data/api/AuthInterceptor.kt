package com.quant.trading.data.api

import com.quant.trading.data.local.SecureStorage
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * OkHttp interceptor that attaches JWT token to every request.
 * If no JWT is available, falls back to API key header.
 */
@Singleton
class AuthInterceptor @Inject constructor(
    private val storage: SecureStorage,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()

        // Skip auth for login endpoint
        if (original.url.encodedPath.endsWith("/auth/login")) {
            return chain.proceed(original)
        }

        val builder = original.newBuilder()

        val token = storage.getJwt()
        if (!token.isNullOrBlank()) {
            builder.addHeader("Authorization", "Bearer $token")
        } else {
            val apiKey = storage.getApiKey()
            if (!apiKey.isNullOrBlank()) {
                builder.addHeader("X-API-Key", apiKey)
            }
        }

        return chain.proceed(builder.build())
    }
}
