import { View, Text, StyleSheet } from "react-native";
import type { OrderInfo } from "@quant/shared";

export function OrderRow({ order }: { order: OrderInfo }) {
  const sideColor = order.side === "BUY" ? "#22C55E" : "#EF4444";
  return (
    <View style={styles.row}>
      <View style={styles.left}>
        <Text style={styles.symbol}>{order.symbol}</Text>
        <Text style={[styles.side, { color: sideColor }]}>{order.side}</Text>
        <Text style={styles.qty}>{order.quantity} @ {order.price != null ? `$${order.price.toFixed(2)}` : "MKT"}</Text>
      </View>
      <View style={styles.right}>
        <Text style={styles.status}>{order.status}</Text>
        <Text style={styles.time}>{new Date(order.created_at).toLocaleDateString()}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#334155",
  },
  left: { flexDirection: "row", alignItems: "center", gap: 8 },
  right: { alignItems: "flex-end" },
  symbol: { color: "#F1F5F9", fontWeight: "600", fontSize: 14 },
  side: { fontWeight: "600", fontSize: 12 },
  qty: { color: "#94A3B8", fontSize: 12 },
  status: { color: "#94A3B8", fontSize: 12 },
  time: { color: "#64748B", fontSize: 11 },
});
