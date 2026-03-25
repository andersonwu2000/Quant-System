package com.quant.trading.data.api

import android.util.Log
import com.quant.trading.data.local.SecureStorage
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * OkHttp interceptor that detects 401 Unauthorized responses and clears
 * stored credentials. This prevents the app from getting stuck in an
 * infinite error loop when the JWT token has expired.
 *
 * The actual navigation back to login is triggered by UI observing
 * the authentication state change.
 */
@Singleton
class UnauthorizedInterceptor @Inject constructor(
    private val storage: SecureStorage,
) : Interceptor {

    companion object {
        private const val TAG = "UnauthorizedInterceptor"
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val response = chain.proceed(request)

        // Skip login endpoint — a 401 there means wrong credentials, not expired token
        if (request.url.encodedPath.endsWith("/auth/login")) {
            return response
        }

        if (response.code == 401) {
            Log.w(TAG, "Received 401 for ${request.url.encodedPath}, clearing credentials")
            storage.clearJwt()
        }

        return response
    }
}
