import { View, Text, StyleSheet } from "react-native";

interface Props {
  label: string;
  value: string;
  color?: string;
  small?: boolean;
}

export function MetricCard({ label, value, color, small }: Props) {
  return (
    <View style={[styles.card, small && styles.cardSmall]}>
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, small && styles.valueSmall, color ? { color } : null]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#1E293B",
    borderRadius: 12,
    padding: 16,
    flex: 1,
    marginHorizontal: 4,
  },
  cardSmall: {
    padding: 12,
  },
  label: {
    color: "#94A3B8",
    fontSize: 12,
    fontWeight: "500",
    marginBottom: 4,
  },
  value: {
    color: "#F1F5F9",
    fontSize: 20,
    fontWeight: "700",
  },
  valueSmall: {
    fontSize: 16,
  },
});
