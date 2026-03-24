package com.quant.trading.di

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.quant.trading.data.api.AuthInterceptor
import com.quant.trading.data.api.QuantApiService
import com.quant.trading.data.api.WebSocketManager
import com.quant.trading.data.local.SecureStorage
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(authInterceptor: AuthInterceptor): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(
                HttpLoggingInterceptor().apply {
                    level = HttpLoggingInterceptor.Level.BODY
                }
            )
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .pingInterval(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(
        okHttpClient: OkHttpClient,
        storage: SecureStorage,
    ): Retrofit {
        val baseUrl = storage.getServerUrl() ?: "http://10.0.2.2:8000/"
        return Retrofit.Builder()
            .baseUrl(baseUrl.trimEnd('/') + "/")
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    @Provides
    @Singleton
    fun provideApiService(retrofit: Retrofit): QuantApiService {
        return retrofit.create(QuantApiService::class.java)
    }

    @Provides
    @Singleton
    fun provideWebSocketManager(
        okHttpClient: OkHttpClient,
        storage: SecureStorage,
    ): WebSocketManager {
        return WebSocketManager(okHttpClient, storage)
    }
}
