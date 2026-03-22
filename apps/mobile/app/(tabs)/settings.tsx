import { View, Text, ScrollView, Pressable, Alert, StyleSheet } from "react-native";
import { useState, useEffect, useCallback } from "react";
import type { SystemStatus, RiskRule } from "../../src/types";
import { system, risk } from "../../src/api/endpoints";
import { useAuth } from "../../src/hooks/useAuth";

export default function SettingsScreen() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [rules, setRules] = useState<RiskRule[]>([]);
  const { logout } = useAuth();

  const loadData = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([system.status(), risk.rules()]);
      setStatus(s);
      setRules(r);
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleRule = async (name: string, enabled: boolean) => {
    try {
      await risk.toggleRule(name, !enabled);
      loadData();
    } catch (err) {
      Alert.alert("Error", err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* System Status */}
      <Text style={styles.sectionTitle}>System</Text>
      {status && (
        <View style={styles.card}>
          <InfoRow label="Mode" value={status.mode} />
          <InfoRow label="Data Source" value={status.data_source} />
          <InfoRow label="Database" value={status.database} />
          <InfoRow label="Strategies Running" value={String(status.strategies_running)} />
          <InfoRow
            label="Uptime"
            value={`${Math.floor(status.uptime_seconds / 3600)}h ${Math.floor((status.uptime_seconds % 3600) / 60)}m`}
          />
        </View>
      )}

      {/* Risk Rules */}
      <Text style={styles.sectionTitle}>Risk Rules</Text>
      <View style={styles.card}>
        {rules.map((rule) => (
          <Pressable
            key={rule.name}
            style={styles.ruleRow}
            onPress={() => toggleRule(rule.name, rule.enabled)}
          >
            <Text style={styles.ruleName}>{rule.name}</Text>
            <View
              style={[
                styles.toggle,
                { backgroundColor: rule.enabled ? "#22C55E" : "#475569" },
              ]}
            >
              <Text style={styles.toggleText}>{rule.enabled ? "ON" : "OFF"}</Text>
            </View>
          </Pressable>
        ))}
      </View>

      {/* Disconnect */}
      <Pressable style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutText}>Disconnect</Text>
      </Pressable>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A", padding: 16 },
  sectionTitle: { color: "#F1F5F9", fontSize: 18, fontWeight: "700", marginBottom: 12, marginTop: 8 },
  card: { backgroundColor: "#1E293B", borderRadius: 12, padding: 4, marginBottom: 20 },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  infoLabel: { color: "#94A3B8", fontSize: 14 },
  infoValue: { color: "#F1F5F9", fontSize: 14, fontWeight: "600" },
  ruleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  ruleName: { color: "#F1F5F9", fontSize: 13, flex: 1 },
  toggle: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 4 },
  toggleText: { color: "#FFFFFF", fontSize: 11, fontWeight: "700" },
  logoutBtn: {
    backgroundColor: "#334155",
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    marginTop: 8,
  },
  logoutText: { color: "#EF4444", fontSize: 15, fontWeight: "600" },
});
