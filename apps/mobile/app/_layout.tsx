import { useEffect, useState } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useAuth } from "../src/hooks/useAuth";

export default function RootLayout() {
  const { authenticated, checkSession } = useAuth();

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#0F172A" },
          headerTintColor: "#F1F5F9",
          contentStyle: { backgroundColor: "#0F172A" },
        }}
      >
        {!authenticated ? (
          <Stack.Screen name="login" options={{ headerShown: false }} />
        ) : (
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        )}
      </Stack>
    </>
  );
}
