import { View, Text, FlatList, RefreshControl, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useState, useEffect, useCallback, useMemo } from "react";
import type { Position } from "@quant/shared";
import { portfolio } from "@quant/shared";
import { PositionRow } from "../../src/components/PositionRow";
import { fmtCurrency } from "../../src/utils/format";
import { useT } from "@/src/i18n";

export default function PositionsScreen() {
  const { t } = useT();
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await portfolio.positions();
      setPositions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load positions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const sorted = useMemo(
    () => positions.slice().sort((a, b) => Math.abs(b.market_value) - Math.abs(a.market_value)),
    [positions],
  );

  const totalMV = positions.reduce((sum, p) => sum + p.market_value, 0);
  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <FlatList
        data={sorted}
        keyExtractor={(item) => item.symbol}
        renderItem={({ item }) => <PositionRow position={item} />}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor="#3B82F6" />
        }
        ListHeaderComponent={
          <>
            {error && <Text style={styles.error}>{error}</Text>}
            <View style={styles.summary}>
              <View style={styles.summaryItem}>
                <Text style={styles.summaryLabel}>{t.portfolio.totalValue}</Text>
                <Text style={styles.summaryValue}>{fmtCurrency(totalMV)}</Text>
              </View>
              <View style={styles.summaryItem}>
                <Text style={styles.summaryLabel}>{t.portfolio.unrealizedPnl}</Text>
                <Text style={[styles.summaryValue, { color: totalPnl >= 0 ? "#22C55E" : "#EF4444" }]}>
                  {fmtCurrency(totalPnl)}
                </Text>
              </View>
            </View>
          </>
        }
        ListEmptyComponent={<Text style={styles.empty}>{t.portfolio.noPositions}</Text>}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A" },
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
  error: { color: "#EF4444", fontSize: 14, textAlign: "center", padding: 12, marginBottom: 8 },
  empty: { color: "#64748B", fontSize: 14, textAlign: "center", padding: 24 },
});
