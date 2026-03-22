import { useEffect, useRef } from "react";
import { WSManager } from "../api/ws";
import type { Channel } from "../api/ws";

export function useWs(channel: Channel, onMessage: (data: unknown) => void) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    const ws = new WSManager(channel);
    ws.connect();
    const unsub = ws.subscribe((d) => handlerRef.current(d));
    return () => { unsub(); ws.disconnect(); };
  }, [channel]);
}
