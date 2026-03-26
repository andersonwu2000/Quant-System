/**
 * WebSocket manager — connects to backend channels with auto-reconnect
 * and exponential backoff. Platform-agnostic: URL builder injected at init.
 */

export type Channel = "portfolio" | "alerts" | "orders" | "market" | "auto-alpha";
type MessageHandler = (data: unknown) => void;
type StatusHandler = (connected: boolean) => void;

const PING_INTERVAL_MS = 30_000;
const MAX_BACKOFF_MS = 60_000;
const BASE_DELAY_MS = 3_000;
const MAX_RETRIES = 20;

let _wsUrlBuilder: ((channel: Channel) => string) | null = null;

export function initWs(urlBuilder: (channel: Channel) => string) {
  _wsUrlBuilder = urlBuilder;
}

export class WSManager {
  private ws: WebSocket | null = null;
  private handlers = new Set<MessageHandler>();
  private statusHandlers = new Set<StatusHandler>();
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private active = true;
  private retries = 0;
  private _connected = false;

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
      this.setConnected(true);
      this.pingTimer = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) this.ws.send("ping");
      }, PING_INTERVAL_MS);
    };

    this.ws.onmessage = (e) => {
      if (e.data === "pong") return;
      try {
        const data = JSON.parse(e.data);
        this.handlers.forEach((h) => {
          try {
            h(data);
          } catch {
            // isolate handler errors to prevent blocking other handlers
          }
        });
      } catch {
        // non-JSON message, skip
      }
    };

    this.ws.onclose = () => {
      this.cleanup();
      this.setConnected(false);
      if (this.active && this.retries < MAX_RETRIES) {
        const delay = Math.min(BASE_DELAY_MS * 2 ** Math.min(this.retries, 6), MAX_BACKOFF_MS);
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

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    handler(this._connected);
    return () => {
      this.statusHandlers.delete(handler);
    };
  }

  get connected(): boolean {
    return this._connected;
  }

  private setConnected(value: boolean) {
    if (this._connected !== value) {
      this._connected = value;
      this.statusHandlers.forEach((h) => h(value));
    }
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
