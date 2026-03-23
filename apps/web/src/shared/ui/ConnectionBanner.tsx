import { WifiOff } from "lucide-react";

interface Props {
  connected: boolean;
  label?: string;
}

export function ConnectionBanner({ connected, label }: Props) {
  if (connected) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex items-center gap-2 bg-amber-500/15 border border-amber-500/30 text-amber-300 text-sm px-4 py-2 rounded-lg mb-4"
    >
      <WifiOff size={16} />
      <span>{label ?? "Live connection lost. Reconnecting…"}</span>
    </div>
  );
}
