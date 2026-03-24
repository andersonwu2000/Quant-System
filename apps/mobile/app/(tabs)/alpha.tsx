import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator } from "react-native";
import { useState } from "react";
import { useT } from "@/src/i18n";
import { alpha as alphaApi } from "@quant/shared";
import { fmtNum, fmtPct } from "@/src/utils/format";
import {
  bg, surface, textPrimary, textSecondary, textMuted,
  blue, blueAlpha, white, warning, warningAlpha,
} from "@/src/theme/colors";
import type { AlphaRunRequest, AlphaReport, FactorReport } from "@quant/shared";

const FACTORS = [
  { name: "momentum",       label: "Momentum" },
  { name: "mean_reversion", label: "Mean Reversion" },
  { name: "volatility",     label: "Volatility" },
  { name: "rsi",            label: "RSI" },
  { name: "ma_cross",       label: "MA Cross" },
  { name: "vpt",            label: "Volume-Price" },
  { name: "reversal",       label: "Reversal" },
  { name: "illiquidity",    label: "Illiquidity" },
  { name: "ivol",           label: "Idio. Vol" },
  { name: "skewness",       label: "Skewness" },
  { name: "max_ret",        label: "Max Return" },
] as const;

type FactorName = typeof FACTORS[number]["name"];

export default function AlphaScreen() {
  const { t } = useT();
  const [selected, setSelected] = useState<Set<FactorName>>(new Set(["momentum", "mean_reversion"]));
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AlphaReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = (name: FactorName) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const run = async () => {
    if (selected.size === 0) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const req: AlphaRunRequest = {
        factors: [...selected].map((name) => ({ name, direction: 1 })),
        universe: ["2330.TW", "2317.TW", "2454.TW", "2412.TW", "2308.TW"],
        start: "2020-01-01",
        end: new Date().toISOString().slice(0, 10),
      };
      const summary = await alphaApi.run(req);
      const deadline = Date.now() + 30 * 60 * 1000;
      let delay = 2000;
      while (true) {
        if (Date.now() > deadline) { setError(t.alpha.timedOut); return; }
        await new Promise((r) => setTimeout(r, delay));
        delay = Math.min(delay * 1.3, 8000);
        const status = await alphaApi.status(summary.task_id);
        if (status.status === "completed") {
          const report = await alphaApi.result(summary.task_id);
          setResult(report);
          return;
        }
        if (status.status === "failed") { setError(status.error ?? t.alpha.failed); return; }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setRunning(false);
    }
  };

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <Text style={s.title}>{t.alpha.title}</Text>

      {/* Factor selector */}
      <Text style={s.sectionLabel}>{t.alpha.factors}</Text>
      <View style={s.chipRow}>
        {FACTORS.map(({ name, label }) => {
          const active = selected.has(name);
          return (
            <TouchableOpacity
              key={name}
              onPress={() => toggle(name)}
              style={[s.chip, active && s.chipActive]}
            >
              <Text style={[s.chipText, active && s.chipTextActive]}>{label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Run button */}
      <TouchableOpacity
        onPress={run}
        disabled={running || selected.size === 0}
        style={[s.runBtn, (running || selected.size === 0) && s.runBtnDisabled]}
      >
        {running
          ? <ActivityIndicator size="small" color={white} />
          : <Text style={s.runBtnText}>{t.alpha.run}</Text>
        }
      </TouchableOpacity>

      {error && (
        <View style={s.errorBox}>
          <Text style={s.errorText}>{error}</Text>
        </View>
      )}

      {/* Results */}
      {result && (
        <View style={s.results}>
          <Text style={s.sectionLabel}>{t.alpha.factorSummary}</Text>

          {/* Header row */}
          <View style={[s.tableRow, s.tableHeader]}>
            <Text style={[s.cell, s.cellFactor, s.headerText]}>{t.alpha.factor}</Text>
            <Text style={[s.cell, s.headerText]}>{t.alpha.icMean}</Text>
            <Text style={[s.cell, s.headerText]}>{t.alpha.icir}</Text>
            <Text style={[s.cell, s.headerText]}>{t.alpha.lsRatio}</Text>
          </View>

          {result.factors.map((f: FactorReport) => (
            <View key={f.name} style={[s.tableRow, s.tableDataRow]}>
              <Text style={[s.cell, s.cellFactor, s.bodyText]}>
                {FACTORS.find((x) => x.name === f.name)?.label ?? f.name}
              </Text>
              <Text style={[s.cell, s.bodyText, f.ic.ic_mean > 0 ? s.positive : s.negative]}>
                {f.ic.ic_mean > 0 ? "+" : ""}{fmtNum(f.ic.ic_mean, 3)}
              </Text>
              <Text style={[s.cell, s.bodyText, f.ic.icir > 0 ? s.positive : s.negative]}>
                {fmtNum(f.ic.icir, 2)}
              </Text>
              <Text style={[s.cell, s.bodyText, f.long_short_sharpe > 0 ? s.positive : s.negative]}>
                {fmtNum(f.long_short_sharpe, 2)}
              </Text>
            </View>
          ))}

          {result.composite_ic && (
            <View style={s.compositeBox}>
              <Text style={s.compositeLabel}>{t.alpha.compositeAlpha}</Text>
              <Text style={s.compositeValue}>
                IC {result.composite_ic.ic_mean > 0 ? "+" : ""}{fmtNum(result.composite_ic.ic_mean, 4)}
                {"  "}ICIR {fmtNum(result.composite_ic.icir, 2)}
              </Text>
            </View>
          )}
        </View>
      )}

    </ScrollView>
  );
}

const s = StyleSheet.create({
  container:  { flex: 1, backgroundColor: bg },
  content:    { padding: 16, paddingBottom: 40, gap: 12 },
  title:      { fontSize: 22, fontWeight: "700", color: textPrimary, marginBottom: 4 },
  sectionLabel: { fontSize: 13, fontWeight: "600", color: textSecondary, marginTop: 8, marginBottom: 6 },
  chipRow:    { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip:       { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, backgroundColor: surface, borderWidth: 1, borderColor: surface },
  chipActive: { backgroundColor: blueAlpha, borderColor: blue },
  chipText:   { fontSize: 12, color: textSecondary },
  chipTextActive: { color: blue, fontWeight: "600" },
  runBtn:     { marginTop: 8, paddingVertical: 14, backgroundColor: blue, borderRadius: 12, alignItems: "center" },
  runBtnDisabled: { opacity: 0.5 },
  runBtnText: { color: white, fontSize: 15, fontWeight: "600" },
  errorBox:   { padding: 12, backgroundColor: "rgba(239,68,68,0.1)", borderRadius: 10 },
  errorText:  { color: "#f87171", fontSize: 13 },
  results:    { gap: 6 },
  tableRow:   { flexDirection: "row", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: surface },
  tableHeader: { borderBottomWidth: 2 },
  tableDataRow: {},
  cell:       { flex: 1, textAlign: "right", fontSize: 12 },
  cellFactor: { flex: 2, textAlign: "left" },
  headerText: { color: textMuted, fontWeight: "600" },
  bodyText:   { color: textPrimary },
  positive:   { color: "#10b981" },
  negative:   { color: "#f87171" },
  compositeBox:  { marginTop: 8, padding: 12, backgroundColor: blueAlpha, borderRadius: 10, gap: 4 },
  compositeLabel: { fontSize: 12, color: textMuted, fontWeight: "600" },
  compositeValue: { fontSize: 14, color: blue, fontWeight: "700" },
  banner:     { padding: 12, backgroundColor: warningAlpha, borderRadius: 10 },
  bannerText: { color: warning, fontSize: 13, fontWeight: "500" },
});
