import { View, Text, ScrollView, RefreshControl, StyleSheet } from "react-native";
import { useState, useEffect, useCallback } from "react";
import type { Position } from "../../src/types";
import { portfolio } from "../../src/api/endpoints";
import { PositionRow } from "../../src/components/PositionRow";
import { fmtCurrency } from "../../src/utils/format";

export default function PositionsScreen() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await portfolio.positions();
      setPositions(data);
    } catch {
      // handled by error boundary
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const totalMV = positions.reduce((sum, p) => sum + p.market_value, 0);
  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={refresh} tintColor="#3B82F6" />
      }
    >
      <View style={styles.summary}>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>Total Value</Text>
          <Text style={styles.summaryValue}>{fmtCurrency(totalMV)}</Text>
        </View>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>Unrealized P&L</Text>
          <Text style={[styles.summaryValue, { color: totalPnl >= 0 ? "#22C55E" : "#EF4444" }]}>
            {fmtCurrency(totalPnl)}
          </Text>
        </View>
      </View>

      {positions.length === 0 ? (
        <Text style={styles.empty}>No open positions</Text>
      ) : (
        positions
          .sort((a, b) => Math.abs(b.market_value) - Math.abs(a.market_value))
          .map((pos) => <PositionRow key={pos.symbol} position={pos} />)
      )}

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A", padding: 16 },
  summary: {
    flexDirection: "row",
    justifyContent: "space-around",
    backgroundColor: "#1E293B",
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  summaryItem: { alignItems: "center" },
  summaryLabel: { color: "#94A3B8", fontSize: 12 },
  summaryValue: { color: "#F1F5F9", fontSize: 20, fontWeight: "700", marginTop: 4 },
  empty: { color: "#64748B", fontSize: 14, textAlign: "center", padding: 24 },
});
