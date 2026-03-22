import { View, Text, ScrollView, RefreshControl, Pressable, Alert, StyleSheet } from "react-native";
import { useAlerts } from "../../src/hooks/useAlerts";
import { AlertItem } from "../../src/components/AlertItem";
import { risk } from "../../src/api/endpoints";

export default function AlertsScreen() {
  const { alerts, loading, refresh } = useAlerts();

  const handleKillSwitch = () => {
    Alert.alert(
      "Kill Switch",
      "This will stop ALL strategies and cancel ALL pending orders. Are you sure?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Confirm",
          style: "destructive",
          onPress: async () => {
            try {
              await risk.killSwitch();
              Alert.alert("Kill Switch", "All strategies stopped, all orders cancelled.");
            } catch (err) {
              Alert.alert("Error", err instanceof Error ? err.message : "Failed");
            }
          },
        },
      ],
    );
  };

  return (
    <View style={styles.container}>
      <Pressable style={styles.killButton} onPress={handleKillSwitch}>
        <Text style={styles.killText}>KILL SWITCH</Text>
      </Pressable>

      <ScrollView
        style={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor="#3B82F6" />
        }
      >
        {alerts.length === 0 ? (
          <Text style={styles.empty}>No risk alerts</Text>
        ) : (
          alerts.map((alert, i) => <AlertItem key={`${alert.timestamp}-${i}`} alert={alert} />)
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A", padding: 16 },
  killButton: {
    backgroundColor: "#DC2626",
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    marginBottom: 20,
  },
  killText: { color: "#FFFFFF", fontSize: 16, fontWeight: "800", letterSpacing: 1 },
  list: { flex: 1 },
  empty: { color: "#64748B", fontSize: 14, textAlign: "center", padding: 24 },
});
