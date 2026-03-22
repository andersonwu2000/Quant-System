import { View, Text, StyleSheet } from "react-native";
import type { RiskAlert } from "../types";
import { fmtTime } from "../utils/format";

interface Props {
  alert: RiskAlert;
}

const severityColors: Record<string, string> = {
  WARNING: "#F59E0B",
  CRITICAL: "#EF4444",
  INFO: "#3B82F6",
};

export function AlertItem({ alert }: Props) {
  const color = severityColors[alert.severity] || "#94A3B8";

  return (
    <View style={styles.row}>
      <View style={[styles.badge, { backgroundColor: color }]}>
        <Text style={styles.badgeText}>{alert.severity}</Text>
      </View>
      <View style={styles.content}>
        <Text style={styles.rule}>{alert.rule_name}</Text>
        <Text style={styles.message} numberOfLines={2}>
          {alert.message}
        </Text>
      </View>
      <Text style={styles.time}>{fmtTime(alert.timestamp)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1E293B",
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    marginRight: 10,
  },
  badgeText: { color: "#FFFFFF", fontSize: 10, fontWeight: "700" },
  content: { flex: 1 },
  rule: { color: "#F1F5F9", fontSize: 14, fontWeight: "600" },
  message: { color: "#94A3B8", fontSize: 12, marginTop: 2 },
  time: { color: "#64748B", fontSize: 11 },
});
