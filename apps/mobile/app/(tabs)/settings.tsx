import { View, Text, ScrollView, Pressable, Alert, StyleSheet, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useState, useEffect, useCallback } from "react";
import type { SystemStatus, RiskRule } from "@quant/shared";
import { system, risk } from "@quant/shared";
import { useAuth } from "../../src/hooks/useAuth";
import { useT } from "@/src/i18n";
import type { Lang } from "@/src/i18n";

export default function SettingsScreen() {
  const { t, lang, setLang } = useT();
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
      Alert.alert(t.common.error, err instanceof Error ? err.message : t.common.failed);
    }
  };

  const langOptions: { key: Lang; label: string }[] = [
    { key: "en", label: "EN" },
    { key: "zh", label: "繁體中文" },
  ];

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
    <ScrollView style={{ flex: 1, padding: 16 }}>
      {/* Language */}
      <Text style={styles.sectionTitle}>{t.settings.language}</Text>
      <View style={styles.card}>
        <View style={styles.langRow}>
          {langOptions.map((opt) => (
            <TouchableOpacity
              key={opt.key}
              style={[styles.langBtn, lang === opt.key && styles.langBtnActive]}
              onPress={() => setLang(opt.key)}
            >
              <Text style={[styles.langBtnText, lang === opt.key && styles.langBtnTextActive]}>
                {opt.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* System Status */}
      <Text style={styles.sectionTitle}>{t.settings.system}</Text>
      {status && (
        <View style={styles.card}>
          <InfoRow label={t.settings.mode} value={status.mode} />
          <InfoRow label={t.settings.dataSource} value={status.data_source} />
          <InfoRow label={t.settings.database} value={status.database} />
          <InfoRow label={t.settings.strategiesRunning} value={String(status.strategies_running)} />
          <InfoRow
            label={t.settings.uptime}
            value={`${Math.floor(status.uptime_seconds / 3600)}h ${Math.floor((status.uptime_seconds % 3600) / 60)}m`}
          />
        </View>
      )}

      {/* Risk Rules */}
      <Text style={styles.sectionTitle}>{t.risk.riskRules}</Text>
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
        <Text style={styles.logoutText}>{t.settings.disconnect}</Text>
      </Pressable>

      <View style={{ height: 40 }} />
    </ScrollView>
    </SafeAreaView>
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
  container: { flex: 1, backgroundColor: "#0F172A" },
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
  langRow: {
    flexDirection: "row",
    padding: 10,
    gap: 8,
  },
  langBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: "#0F172A",
    alignItems: "center",
  },
  langBtnActive: {
    backgroundColor: "rgba(59, 130, 246, 0.2)",
  },
  langBtnText: {
    color: "#94A3B8",
    fontSize: 14,
    fontWeight: "600",
  },
  langBtnTextActive: {
    color: "#60A5FA",
  },
});
