import { View, Text, FlatList, RefreshControl, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useState, useEffect, useCallback, useMemo } from "react";
import type { Position } from "@quant/shared";
import { portfolio } from "@quant/shared";
import { PositionRow } from "../../src/components/PositionRow";
import { fmtCurrency } from "../../src/utils/format";
import { useT } from "@/src/i18n";
import { bg, surface, textSecondary, textPrimary, blue, success, danger, textMuted } from "@/src/theme/colors";

const POSITION_ROW_HEIGHT = 64; // padding 14*2 + content ~28 + marginBottom 8

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
        getItemLayout={(_data, index) => ({
          length: POSITION_ROW_HEIGHT,
          offset: POSITION_ROW_HEIGHT * index,
          index,
        })}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor={blue} />
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
                <Text style={[styles.summaryValue, { color: totalPnl >= 0 ? success : danger }]}>
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
  container: { flex: 1, backgroundColor: bg },
  summary: {
    flexDirection: "row",
    justifyContent: "space-around",
    backgroundColor: surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  summaryItem: { alignItems: "center" },
  summaryLabel: { color: textSecondary, fontSize: 12 },
  summaryValue: { color: textPrimary, fontSize: 20, fontWeight: "700", marginTop: 4 },
  error: { color: danger, fontSize: 14, textAlign: "center", padding: 12, marginBottom: 8 },
  empty: { color: textMuted, fontSize: 14, textAlign: "center", padding: 24 },
});
