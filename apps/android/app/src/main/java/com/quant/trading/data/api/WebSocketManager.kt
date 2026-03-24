package com.quant.trading.data.api

import android.util.Log
import com.quant.trading.data.local.SecureStorage
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.*
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.min

/**
 * WebSocket manager with auto-reconnect and exponential backoff.
 * Mirrors apps/shared/src/api/ws.ts WSManager behaviour.
 */
@Singleton
class WebSocketManager @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val storage: SecureStorage,
) {
    companion object {
        private const val TAG = "WebSocketManager"
        private const val BASE_DELAY_MS = 3_000L
        private const val MAX_DELAY_MS = 60_000L
        private const val PING_INTERVAL_MS = 30_000L
    }

    enum class Channel { PORTFOLIO, ALERTS, ORDERS, MARKET }

    data class WsMessage(val channel: Channel, val raw: String)

    private val _messages = MutableSharedFlow<WsMessage>(extraBufferCapacity = 64)
    val messages: SharedFlow<WsMessage> = _messages

    private val connections = mutableMapOf<Channel, WebSocket>()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var retryCount = mutableMapOf<Channel, Int>()

    fun connect(channel: Channel) {
        if (connections.containsKey(channel)) return

        val baseUrl = storage.getServerUrl() ?: return
        val token = storage.getJwt() ?: ""
        val wsUrl = baseUrl
            .replace("http://", "ws://")
            .replace("https://", "wss://")
            .trimEnd('/') + "/ws/${channel.name.lowercase()}?token=$token"

        val request = Request.Builder().url(wsUrl).build()
        val ws = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "Connected to ${channel.name}")
                retryCount[channel] = 0
                // Start ping
                scope.launch {
                    while (isActive && connections[channel] == webSocket) {
                        delay(PING_INTERVAL_MS)
                        webSocket.send("""{"type":"ping"}""")
                    }
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                _messages.tryEmit(WsMessage(channel, text))
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "WS failure on ${channel.name}: ${t.message}")
                connections.remove(channel)
                scheduleReconnect(channel)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WS closed ${channel.name}: $reason")
                connections.remove(channel)
            }
        })

        connections[channel] = ws
    }

    fun disconnect(channel: Channel) {
        connections.remove(channel)?.close(1000, "Client disconnect")
    }

    fun disconnectAll() {
        connections.keys.toList().forEach { disconnect(it) }
    }

    private fun scheduleReconnect(channel: Channel) {
        val count = retryCount.getOrDefault(channel, 0)
        retryCount[channel] = count + 1
        val delay = min(BASE_DELAY_MS * (1L shl min(count, 5)), MAX_DELAY_MS)

        scope.launch {
            delay(delay)
            Log.d(TAG, "Reconnecting ${channel.name} (attempt ${count + 1})")
            connect(channel)
        }
    }
}
