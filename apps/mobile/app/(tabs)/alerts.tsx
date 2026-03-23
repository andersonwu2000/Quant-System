import { View, Text, FlatList, RefreshControl, Pressable, Alert, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAlerts } from "../../src/hooks/useAlerts";
import { AlertItem } from "../../src/components/AlertItem";
import { risk } from "@quant/shared";
import { useT } from "@/src/i18n";
import { bg, dangerDark, white, dangerLight, textMuted, blue } from "@/src/theme/colors";

const ALERT_ITEM_HEIGHT = 56; // padding 12*2 + content ~24 + marginBottom 8

export default function AlertsScreen() {
  const { t } = useT();
  const { alerts, loading, refresh } = useAlerts();

  // TODO: killSwitch requires risk_manager role on backend but mobile has no
  // role-based UI gating yet. The backend will reject unauthorized requests,
  // but ideally the UI should hide/disable the button for insufficient roles.
  const handleKillSwitch = () => {
    Alert.alert(
      t.risk.killSwitch,
      t.risk.killConfirm,
      [
        { text: t.common.cancel, style: "cancel" },
        {
          text: t.common.confirm,
          style: "destructive",
          onPress: async () => {
            try {
              await risk.killSwitch();
              Alert.alert(t.risk.killSwitch, t.risk.allStopped);
            } catch (err) {
              Alert.alert(t.common.error, err instanceof Error ? err.message : t.common.failed);
            }
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <FlatList
        data={alerts}
        keyExtractor={(item, i) => `${item.timestamp}-${i}`}
        renderItem={({ item }) => <AlertItem alert={item} />}
        getItemLayout={(_data, index) => ({
          length: ALERT_ITEM_HEIGHT,
          offset: ALERT_ITEM_HEIGHT * index,
          index,
        })}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor={blue} />
        }
        ListEmptyComponent={<Text style={styles.empty}>{t.risk.noAlerts}</Text>}
        ListFooterComponent={
          <Pressable
            style={styles.killButton}
            onLongPress={handleKillSwitch}
            delayLongPress={1000}
          >
            <Text style={styles.killText}>{t.risk.killSwitch.toUpperCase()}</Text>
            <Text style={styles.killHint}>{t.common.longPressHint}</Text>
          </Pressable>
        }
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: bg },
  killButton: {
    backgroundColor: dangerDark,
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    marginTop: 24,
  },
  killText: { color: white, fontSize: 16, fontWeight: "800", letterSpacing: 1 },
  killHint: { color: dangerLight, fontSize: 11, marginTop: 4 },
  empty: { color: textMuted, fontSize: 14, textAlign: "center", padding: 24 },
});
