import { useEffect, useRef, useState } from "react";
import { WSManager } from "@quant/shared";
import type { Channel } from "@quant/shared";

export function useWs(channel: Channel, onMessage: (data: unknown) => void) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WSManager(channel);
    ws.connect();
    const unsub = ws.subscribe((d) => handlerRef.current(d));
    const unsubStatus = ws.onStatus(setConnected);
    return () => { unsub(); unsubStatus(); ws.disconnect(); };
  }, [channel]);

  return { connected };
}
