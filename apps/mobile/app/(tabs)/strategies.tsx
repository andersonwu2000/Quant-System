import { View, Text, FlatList, RefreshControl, Alert, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useState, useEffect, useCallback } from "react";
import type { StrategyInfo } from "@quant/shared";
import { strategies as api } from "@quant/shared";
import { StrategyRow } from "../../src/components/StrategyRow";
import { useT } from "@/src/i18n";
import { bg, textSecondary, textMuted, blue } from "@/src/theme/colors";

const STRATEGY_ROW_HEIGHT = 64; // padding 14*2 + content ~28 + marginBottom 8

export default function StrategiesScreen() {
  const { t } = useT();
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
        Alert.alert(t.common.error, err instanceof Error ? err.message : t.common.operationFailed);
      }
    },
    [refresh, t],
  );

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <FlatList
        data={items}
        keyExtractor={(item) => item.name}
        renderItem={({ item }) => <StrategyRow strategy={item} onToggle={handleToggle} />}
        getItemLayout={(_data, index) => ({
          length: STRATEGY_ROW_HEIGHT,
          offset: STRATEGY_ROW_HEIGHT * index,
          index,
        })}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor={blue} />
        }
        ListHeaderComponent={
          <Text style={styles.header}>
            {items.filter((s) => s.status === "running").length} {t.common.of} {items.length} {t.strategies.running}
          </Text>
        }
        ListEmptyComponent={<Text style={styles.empty}>{t.strategies.noRegistered}</Text>}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: bg },
  header: { color: textSecondary, fontSize: 13, marginBottom: 16 },
  empty: { color: textMuted, fontSize: 14, textAlign: "center", padding: 24 },
});
