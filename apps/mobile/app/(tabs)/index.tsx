import { View, Text, ScrollView, RefreshControl, StyleSheet } from "react-native";
import { usePortfolio } from "../../src/hooks/usePortfolio";
import { MetricCard } from "../../src/components/MetricCard";
import { PositionRow } from "../../src/components/PositionRow";
import { fmtCurrency, fmtPct, pnlColor } from "../../src/utils/format";

export default function DashboardScreen() {
  const { data, loading, refresh } = usePortfolio();

  if (!data) {
    return (
      <View style={styles.center}>
        <Text style={styles.loading}>Loading...</Text>
      </View>
    );
  }

  const dailyColor = pnlColor(data.daily_pnl);

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={refresh} tintColor="#3B82F6" />
      }
    >
      {/* NAV Header */}
      <View style={styles.navHeader}>
        <Text style={styles.navLabel}>Net Asset Value</Text>
        <Text style={styles.navValue}>{fmtCurrency(data.nav)}</Text>
        <Text style={[styles.dailyPnl, { color: dailyColor }]}>
          {fmtCurrency(data.daily_pnl)} ({fmtPct(data.daily_pnl_pct)}) today
        </Text>
      </View>

      {/* Key Metrics */}
      <View style={styles.metricsRow}>
        <MetricCard label="Cash" value={fmtCurrency(data.cash)} small />
        <MetricCard label="Exposure" value={fmtCurrency(data.gross_exposure)} small />
        <MetricCard label="Positions" value={String(data.positions_count)} small />
      </View>

      {/* Top Positions */}
      <Text style={styles.sectionTitle}>Positions</Text>
      {data.positions.length === 0 ? (
        <Text style={styles.empty}>No open positions</Text>
      ) : (
        data.positions
          .sort((a, b) => Math.abs(b.market_value) - Math.abs(a.market_value))
          .slice(0, 10)
          .map((pos) => <PositionRow key={pos.symbol} position={pos} />)
      )}

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A", padding: 16 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0F172A" },
  loading: { color: "#64748B", fontSize: 16 },
  navHeader: { alignItems: "center", paddingVertical: 24 },
  navLabel: { color: "#94A3B8", fontSize: 14 },
  navValue: { color: "#F1F5F9", fontSize: 36, fontWeight: "800", marginTop: 4 },
  dailyPnl: { fontSize: 14, fontWeight: "600", marginTop: 4 },
  metricsRow: { flexDirection: "row", marginBottom: 24 },
  sectionTitle: { color: "#F1F5F9", fontSize: 18, fontWeight: "700", marginBottom: 12 },
  empty: { color: "#64748B", fontSize: 14, textAlign: "center", padding: 24 },
});
