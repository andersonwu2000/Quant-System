/**
 * WebSocket manager — connects to backend channels with auto-reconnect
 * and exponential backoff. Platform-agnostic: URL builder injected at init.
 */

export type Channel = "portfolio" | "alerts" | "orders" | "market";
type MessageHandler = (data: unknown) => void;

const PING_INTERVAL_MS = 30_000;
const MAX_BACKOFF_MS = 60_000;
const BASE_DELAY_MS = 3_000;

let _wsUrlBuilder: ((channel: Channel) => string) | null = null;

export function initWs(urlBuilder: (channel: Channel) => string) {
  _wsUrlBuilder = urlBuilder;
}

export class WSManager {
  private ws: WebSocket | null = null;
  private handlers = new Set<MessageHandler>();
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private active = true;
  private retries = 0;

  constructor(private channel: Channel) {}

  connect() {
    if (!_wsUrlBuilder) throw new Error("WS not initialized — call initWs() first");

    this.active = true;
    this.cleanup();

    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.ws = new WebSocket(_wsUrlBuilder(this.channel));

    this.ws.onopen = () => {
      this.retries = 0;
      this.pingTimer = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) this.ws.send("ping");
      }, PING_INTERVAL_MS);
    };

    this.ws.onmessage = (e) => {
      if (e.data === "pong") return;
      try {
        const data = JSON.parse(e.data);
        this.handlers.forEach((h) => h(data));
      } catch {
        // non-JSON message, skip
      }
    };

    this.ws.onclose = () => {
      this.cleanup();
      if (this.active) {
        const delay = Math.min(BASE_DELAY_MS * 2 ** this.retries, MAX_BACKOFF_MS);
        this.retries++;
        this.reconnectTimer = setTimeout(() => this.connect(), delay);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    this.active = false;
    this.cleanup();
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close();
      this.ws = null;
    }
  }

  subscribe(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  private cleanup() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
