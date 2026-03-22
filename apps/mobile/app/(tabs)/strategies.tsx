import { View, Text, ScrollView, RefreshControl, Alert, StyleSheet } from "react-native";
import { useState, useEffect, useCallback } from "react";
import type { StrategyInfo } from "../../src/types";
import { strategies as api } from "../../src/api/endpoints";
import { StrategyRow } from "../../src/components/StrategyRow";

export default function StrategiesScreen() {
  const [items, setItems] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.list();
      setItems(data);
    } catch {
      // handled by error boundary
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleToggle = useCallback(
    async (name: string, isRunning: boolean) => {
      try {
        if (isRunning) {
          await api.stop(name);
        } else {
          await api.start(name);
        }
        refresh();
      } catch (err) {
        Alert.alert("Error", err instanceof Error ? err.message : "Operation failed");
      }
    },
    [refresh],
  );

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={refresh} tintColor="#3B82F6" />
      }
    >
      <Text style={styles.header}>
        {items.filter((s) => s.status === "running").length} of {items.length} running
      </Text>

      {items.map((s) => (
        <StrategyRow key={s.name} strategy={s} onToggle={handleToggle} />
      ))}

      {items.length === 0 && (
        <Text style={styles.empty}>No strategies registered</Text>
      )}

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A", padding: 16 },
  header: { color: "#94A3B8", fontSize: 13, marginBottom: 16 },
  empty: { color: "#64748B", fontSize: 14, textAlign: "center", padding: 24 },
});
