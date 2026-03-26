import { useEffect, useRef, useState } from "react";
import { WSManager } from "@quant/shared";
import type { Channel } from "@quant/shared";

/**
 * Shared WSManager instances per channel.
 * Prevents multiple components subscribing to the same channel
 * from creating duplicate WebSocket connections.
 */
const _instances = new Map<Channel, { ws: WSManager; refCount: number }>();

function acquireWs(channel: Channel): WSManager {
  const existing = _instances.get(channel);
  if (existing) {
    existing.refCount++;
    return existing.ws;
  }
  const ws = new WSManager(channel);
  ws.connect();
  _instances.set(channel, { ws, refCount: 1 });
  return ws;
}

function releaseWs(channel: Channel): void {
  const entry = _instances.get(channel);
  if (!entry) return;
  entry.refCount--;
  if (entry.refCount <= 0) {
    entry.ws.disconnect();
    _instances.delete(channel);
  }
}

export function useWs(channel: Channel, onMessage: (data: unknown) => void) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = acquireWs(channel);
    const unsub = ws.subscribe((d) => handlerRef.current(d));
    const unsubStatus = ws.onStatus(setConnected);
    return () => {
      unsub();
      unsubStatus();
      releaseWs(channel);
    };
  }, [channel]);

  return { connected };
}
