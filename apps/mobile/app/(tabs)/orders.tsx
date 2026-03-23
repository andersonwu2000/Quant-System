import { View, FlatList, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useState } from "react";
import { useOrders } from "@/src/hooks/useOrders";
import { OrderRow } from "@/src/components/OrderRow";
import { useT } from "@/src/i18n";
import { bg, surface, blueAlpha, textSecondary, blueLight, danger, textMuted } from "@/src/theme/colors";

const FILTERS = ["all", "filled", "pending"] as const;
const ORDER_ROW_HEIGHT = 49; // paddingVertical 12*2 + content ~25 + hairlineWidth border

export default function OrdersScreen() {
  const { t } = useT();
  const [filter, setFilter] = useState("all");
  const { data, loading, error, refresh } = useOrders(filter);

  return (
    <View style={styles.container}>
      <View style={styles.filterRow}>
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f}
            onPress={() => setFilter(f)}
            style={[styles.filterBtn, filter === f && styles.filterActive]}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {f === "all" ? t.orders.all : f === "filled" ? t.orders.filled : t.orders.pending}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={data}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <OrderRow order={item} />}
        getItemLayout={(_data, index) => ({
          length: ORDER_ROW_HEIGHT,
          offset: ORDER_ROW_HEIGHT * index,
          index,
        })}
        refreshing={loading}
        onRefresh={refresh}
        ListEmptyComponent={!loading ? <Text style={styles.empty}>{t.orders.noOrders}</Text> : null}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: bg },
  filterRow: { flexDirection: "row", padding: 12, gap: 8 },
  filterBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: surface },
  filterActive: { backgroundColor: blueAlpha },
  filterText: { color: textSecondary, fontSize: 13, fontWeight: "500" },
  filterTextActive: { color: blueLight },
  error: { color: danger, padding: 12, fontSize: 13 },
  empty: { color: textMuted, textAlign: "center", paddingTop: 40, fontSize: 14 },
});
