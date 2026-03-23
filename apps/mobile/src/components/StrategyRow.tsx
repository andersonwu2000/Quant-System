import { View, Text, Pressable, Alert, StyleSheet } from "react-native";
import type { StrategyInfo } from "@quant/shared";
import { fmtCurrency, pnlColor } from "../utils/format";
import { surface, textPrimary, success, textMuted, textSecondary, danger, white } from "@/src/theme/colors";

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
            style={[styles.dot, { backgroundColor: isRunning ? success : textMuted }]}
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
          onPress={() => {
            const action = isRunning ? "Stop" : "Start";
            Alert.alert(
              `${action} Strategy`,
              `${action} "${strategy.name}"?`,
              [
                { text: "Cancel", style: "cancel" },
                { text: action, style: isRunning ? "destructive" : "default", onPress: () => onToggle(strategy.name, isRunning) },
              ],
            );
          }}
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
    backgroundColor: surface,
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
  },
  left: { flex: 1 },
  right: { alignItems: "flex-end" },
  name: { color: textPrimary, fontSize: 16, fontWeight: "700" },
  statusRow: { flexDirection: "row", alignItems: "center", marginTop: 4 },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  statusText: { color: textSecondary, fontSize: 12 },
  pnl: { fontSize: 14, fontWeight: "600", marginBottom: 8 },
  button: { paddingHorizontal: 16, paddingVertical: 6, borderRadius: 6 },
  startBtn: { backgroundColor: success },
  stopBtn: { backgroundColor: danger },
  btnText: { color: white, fontSize: 13, fontWeight: "600" },
});
