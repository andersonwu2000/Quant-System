import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useT } from "@/src/i18n";
import { bg, surface, textPrimary, blue, textMuted } from "@/src/theme/colors";

export default function TabLayout() {
  const { t } = useT();

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: bg },
        headerTintColor: textPrimary,
        tabBarStyle: {
          backgroundColor: bg,
          borderTopColor: surface,
        },
        tabBarActiveTintColor: blue,
        tabBarInactiveTintColor: textMuted,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t.nav.dashboard,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="stats-chart" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="positions"
        options={{
          title: t.nav.portfolio,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="briefcase" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="orders"
        options={{
          title: t.nav.orders,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="list-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="strategies"
        options={{
          title: t.nav.strategies,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="bulb" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="backtest"
        options={{
          title: t.nav.backtest,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="flask-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="alpha"
        options={{
          title: t.nav.alpha,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="analytics-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="alerts"
        options={{
          title: t.nav.risk,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="warning" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: t.nav.settings,
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="settings" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
