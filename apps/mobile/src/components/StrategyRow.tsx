import { View, Text, Pressable, StyleSheet } from "react-native";
import type { StrategyInfo } from "../types";
import { fmtCurrency, pnlColor } from "../utils/format";

interface Props {
  strategy: StrategyInfo;
  onToggle: (name: string, running: boolean) => void;
}

export function StrategyRow({ strategy, onToggle }: Props) {
  const isRunning = strategy.status === "running";

  return (
    <View style={styles.row}>
      <View style={styles.left}>
        <Text style={styles.name}>{strategy.name}</Text>
        <View style={styles.statusRow}>
          <View
            style={[styles.dot, { backgroundColor: isRunning ? "#22C55E" : "#64748B" }]}
          />
          <Text style={styles.statusText}>{strategy.status}</Text>
        </View>
      </View>
      <View style={styles.right}>
        <Text style={[styles.pnl, { color: pnlColor(strategy.pnl) }]}>
          {fmtCurrency(strategy.pnl)}
        </Text>
        <Pressable
          style={[styles.button, isRunning ? styles.stopBtn : styles.startBtn]}
          onPress={() => onToggle(strategy.name, isRunning)}
        >
          <Text style={styles.btnText}>{isRunning ? "Stop" : "Start"}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#1E293B",
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
  },
  left: { flex: 1 },
  right: { alignItems: "flex-end" },
  name: { color: "#F1F5F9", fontSize: 16, fontWeight: "700" },
  statusRow: { flexDirection: "row", alignItems: "center", marginTop: 4 },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  statusText: { color: "#94A3B8", fontSize: 12 },
  pnl: { fontSize: 14, fontWeight: "600", marginBottom: 8 },
  button: { paddingHorizontal: 16, paddingVertical: 6, borderRadius: 6 },
  startBtn: { backgroundColor: "#22C55E" },
  stopBtn: { backgroundColor: "#EF4444" },
  btnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600" },
});
