import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";

export function Skeleton({ width = "100%" as const, height = 16 }: { width?: number | `${number}%`; height?: number }) {
  const opacity = useRef(new Animated.Value(0.3)).current;
  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.7, duration: 800, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.3, duration: 800, useNativeDriver: true }),
      ])
    );
    anim.start();
    return () => anim.stop();
  }, [opacity]);

  return <Animated.View style={[styles.skeleton, { width, height, opacity }]} />;
}

export function MetricCardSkeleton() {
  return (
    <View style={styles.card}>
      <Skeleton width={60} height={12} />
      <Skeleton width={90} height={18} />
    </View>
  );
}

const styles = StyleSheet.create({
  skeleton: { backgroundColor: "#334155", borderRadius: 4 },
  card: { backgroundColor: "#1E293B", borderRadius: 12, padding: 14, gap: 6, width: "48%" },
});
